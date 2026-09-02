import hashlib
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from automation_engine.integracoes.google_drive import (
    conectar_google_drive,
    ler_relatorio_json,
    listar_empresas_drive,
    listar_relatorios_json,
)
from src.models.empresa_relatorio import EmpresaRelatorio, RelatorioDriveProcessado
from src.models.user import db


relatorio_bp = Blueprint("relatorio", __name__)
_lock_acumulacao = threading.Lock()


def _inteiro_nao_negativo(valor, padrao=0):
    try:
        return max(0, int(valor))
    except (TypeError, ValueError):
        return padrao


def _nome_empresa(empresa):
    if not isinstance(empresa, dict):
        return ""
    for chave in ("nome", "empresa", "nome_empresa", "razao_social"):
        valor = str(empresa.get(chave) or "").strip()
        if valor:
            return valor
    return ""


def _cnpj_empresa(empresa):
    if not isinstance(empresa, dict):
        return ""
    for chave in ("cnpj", "cpf_cnpj", "documento"):
        valor = str(empresa.get(chave) or "").strip()
        if valor:
            return re.sub(r"\D", "", valor)
    return ""


def _limpar_nome_empresa(nome):
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))
    texto = texto.replace("/", " ")
    texto = re.sub(r"[-–—_]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" -")
    return texto.strip()


def _extrair_cnpj_da_empresa(empresa):
    if not isinstance(empresa, dict):
        return empresa

    empresa = dict(empresa)
    nome = _nome_empresa(empresa)
    cnpj = _cnpj_empresa(empresa)
    if not cnpj and nome:
        match = re.search(r"(\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", nome)
        if match:
            cnpj = re.sub(r"\D", "", match.group(1))
            nome_sem_cnpj = nome[: match.start()] + nome[match.end() :]
            nome = _limpar_nome_empresa(nome_sem_cnpj)
            empresa["nome"] = nome
            empresa["empresa"] = nome
            empresa["cnpj"] = cnpj

    if "nome" not in empresa and nome:
        empresa["nome"] = nome
    if "empresa" not in empresa and nome:
        empresa["empresa"] = nome
    if cnpj and not empresa.get("cnpj"):
        empresa["cnpj"] = cnpj
    if not empresa.get("cnpj") and nome:
        empresa["nome"] = _limpar_nome_empresa(nome)
    if empresa.get("cnpj") and not empresa.get("nome"):
        empresa["nome"] = _limpar_nome_empresa(empresa.get("empresa") or "")

    return empresa


def _chave_empresa(empresa):
    empresa = _extrair_cnpj_da_empresa(empresa)
    cnpj = _cnpj_empresa(empresa)
    if cnpj:
        return f"cnpj:{cnpj}"

    nome = _nome_empresa(empresa)
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(letra for letra in nome if not unicodedata.combining(letra))
    nome = re.sub(r"[^a-z0-9]+", " ", nome.casefold()).strip()
    return f"nome:{nome}" if nome else None


def _deduplicar_empresas(empresas):
    unicas = {}
    for empresa in empresas:
        if not isinstance(empresa, dict):
            continue
        empresa = _extrair_cnpj_da_empresa(empresa)
        chave = _chave_empresa(empresa)
        if chave:
            unicas[chave] = empresa
    return list(unicas.values())


def _chave_nome(empresa):
    nome = unicodedata.normalize("NFKD", str(empresa.get("nome") or ""))
    nome = "".join(letra for letra in nome if not unicodedata.combining(letra))
    return re.sub(r"[^a-z0-9]+", " ", nome.casefold()).strip()


def _mesclar_empresa_base(empresa_base, empresa_complemento):
    empresa = dict(empresa_base or {})
    complemento = dict(empresa_complemento or {})

    cnpj_base = re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
    cnpj_comp = re.sub(r"\D", "", str(complemento.get("cnpj") or ""))
    if cnpj_comp and not cnpj_base:
        empresa["cnpj"] = cnpj_comp
    elif cnpj_base and not cnpj_comp:
        complemento["cnpj"] = cnpj_base

    nome_base = str(empresa.get("nome") or "").strip()
    nome_comp = str(complemento.get("nome") or "").strip()
    if not nome_base and nome_comp:
        empresa["nome"] = nome_comp
    elif nome_base and not nome_comp:
        complemento["nome"] = nome_base

    if nome_base and nome_comp and nome_base.lower() != nome_comp.lower():
        empresa["nome"] = nome_base or nome_comp
        if not empresa.get("cnpj") and complemento.get("cnpj"):
            empresa["cnpj"] = complemento["cnpj"]

    empresa = _extrair_cnpj_da_empresa(empresa)
    if not empresa.get("nome"):
        empresa["nome"] = nome_base or nome_comp or "Empresa não informada"
    return empresa


def _sucessos_por_empresas_drive(empresas_drive, falhas, sucessos_explicitos):
    """No Drive, toda empresa sem falha é considerada um sucesso."""
    falhas_normalizadas = [_extrair_cnpj_da_empresa(dict(empresa)) for empresa in falhas]
    nomes_com_falha = {_chave_nome(empresa) for empresa in falhas_normalizadas}
    nomes_com_falha.discard("")
    cnpjs_com_falha = {
        re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
        for empresa in falhas_normalizadas
        if re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
    }

    sucessos_por_chave = {}
    for empresa in sucessos_explicitos:
        empresa = _extrair_cnpj_da_empresa(dict(empresa))
        chave = _chave_empresa(empresa)
        if not chave:
            continue
        if empresa.get("cnpj") and empresa["cnpj"] in cnpjs_com_falha:
            continue
        nome_chave = _chave_nome(empresa)
        if nome_chave and nome_chave in nomes_com_falha:
            continue
        sucessos_por_chave[chave] = empresa

    for empresa_drive in empresas_drive:
        empresa_drive = _extrair_cnpj_da_empresa(dict(empresa_drive))
        chave_drive = _chave_empresa(empresa_drive)
        if not chave_drive:
            continue
        if empresa_drive.get("cnpj") and empresa_drive["cnpj"] in cnpjs_com_falha:
            continue
        nome_drive = _chave_nome(empresa_drive)
        if nome_drive and nome_drive in nomes_com_falha:
            continue

        empresa_existente = sucessos_por_chave.get(chave_drive)
        if empresa_existente is not None:
            sucessos_por_chave[chave_drive] = _mesclar_empresa_base(
                empresa_existente,
                empresa_drive,
            )
            continue

        chave_compat = None
        for chave, empresa in sucessos_por_chave.items():
            cnpj = re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
            if cnpj and cnpj == empresa_drive.get("cnpj"):
                chave_compat = chave
                break
            if _chave_nome(empresa) == nome_drive:
                chave_compat = chave
                break

        if chave_compat is not None:
            sucessos_por_chave[chave_compat] = _mesclar_empresa_base(
                sucessos_por_chave[chave_compat],
                empresa_drive,
            )
            continue

        sucessos_por_chave.setdefault(chave_drive, empresa_drive)

    return sorted(
        sucessos_por_chave.values(),
        key=lambda empresa: (_chave_nome(empresa), str(empresa.get("cnpj") or "")),
    )


def _normalizar_relatorio(dados):
    resumo = dados.get("resumo")
    falhas = dados.get("empresas_com_falha")
    if not isinstance(resumo, dict) or not isinstance(falhas, list):
        raise ValueError("O JSON do Drive não possui o formato esperado.")

    sucessos = []
    for nome in (
        "empresas_com_sucesso",
        "empresas_certas",
        "empresas_corretas",
    ):
        lista = dados.get(nome)
        if isinstance(lista, list):
            sucessos.extend(lista)

    dados["empresas_com_falha"] = _deduplicar_empresas(falhas)
    dados["empresas_com_sucesso"] = _deduplicar_empresas(sucessos)
    resumo["sucessos"] = len(dados["empresas_com_sucesso"])
    return dados


def _pasta_com_credenciais():
    configurada = os.getenv("GOOGLE_DRIVE_CREDENCIAIS_DIR", "").strip()
    if configurada:
        pasta_configurada = Path(configurada).expanduser()
        if not pasta_configurada.is_absolute():
            pasta_configurada = Path(__file__).resolve().parents[2] / pasta_configurada
        return pasta_configurada.resolve()

    raiz = Path(__file__).resolve().parents[2]
    candidatas = (raiz / "automation_engine", raiz, raiz.parent)
    return next(
        (pasta for pasta in candidatas if (pasta / "credentials.json").exists()),
        raiz,
    )


def _chave_relatorio(arquivo, dados=None):
    arquivo_id = str(arquivo.get("id") or "")
    modificado_em = str(arquivo.get("modifiedTime") or "")
    if arquivo_id and modificado_em:
        return f"{arquivo_id}:{modificado_em}"

    serializado = json.dumps(dados or arquivo, ensure_ascii=False, sort_keys=True)
    return "conteudo:" + hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _atualizar_empresa(empresa, status, dados, arquivo):
    chave = _chave_empresa(empresa)
    if not chave:
        return

    registro = EmpresaRelatorio.query.filter_by(chave=chave).first()
    nome = str(empresa.get("nome") or "").strip()
    cnpj = re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
    momento = str(dados.get("executado_em") or arquivo.get("modifiedTime") or "")
    arquivo_nome = str(arquivo.get("name") or "")

    if registro is None:
        registro = EmpresaRelatorio(
            chave=chave,
            cnpj=cnpj or None,
            nome=nome or "Empresa não informada",
            motivo=str(empresa.get("motivo") or "").strip() or None,
            status=status,
            primeira_ocorrencia=momento or None,
            ultima_ocorrencia=momento or None,
            primeiro_arquivo=arquivo_nome or None,
            ultimo_arquivo=arquivo_nome or None,
            ocorrencias=1,
        )
        db.session.add(registro)
        return

    if cnpj:
        registro.cnpj = cnpj
    if nome:
        registro.nome = nome
    motivo = str(empresa.get("motivo") or "").strip()
    if motivo:
        registro.motivo = motivo
    registro.status = status
    registro.ultima_ocorrencia = momento or registro.ultima_ocorrencia
    registro.ultimo_arquivo = arquivo_nome or registro.ultimo_arquivo
    registro.ocorrencias = (registro.ocorrencias or 0) + 1


def _acumular_relatorio(dados, arquivo):
    chave = _chave_relatorio(arquivo, dados)
    if RelatorioDriveProcessado.query.filter_by(chave=chave).first():
        return False

    # Em conflito dentro do mesmo arquivo, falha prevalece. Uma mudança para
    # sucesso só ocorre quando o CNPJ aparece explicitamente na lista de
    # sucessos de um relatório posterior.
    for empresa in dados["empresas_com_sucesso"]:
        _atualizar_empresa(empresa, "sucesso", dados, arquivo)
    for empresa in dados["empresas_com_falha"]:
        _atualizar_empresa(empresa, "falha", dados, arquivo)

    resumo = dados["resumo"]
    db.session.add(
        RelatorioDriveProcessado(
            chave=chave,
            arquivo_id=str(arquivo.get("id") or "") or None,
            arquivo_nome=str(arquivo.get("name") or "") or None,
            arquivo_modificado_em=str(arquivo.get("modifiedTime") or "") or None,
            titulo=str(dados.get("titulo") or "") or None,
            executado_em=str(dados.get("executado_em") or "") or None,
            total_sucessos=_inteiro_nao_negativo(resumo.get("sucessos")),
            total_ignorados=_inteiro_nao_negativo(resumo.get("ignorados")),
            total_falhas=_inteiro_nao_negativo(
                resumo.get("falhas"), len(dados["empresas_com_falha"])
            ),
        )
    )
    db.session.commit()
    return True


def _montar_relatorio_acumulado():
    falhas = EmpresaRelatorio.query.filter_by(status="falha").order_by(
        EmpresaRelatorio.nome
    ).all()
    sucessos = EmpresaRelatorio.query.filter_by(status="sucesso").order_by(
        EmpresaRelatorio.nome
    ).all()
    ultimo = RelatorioDriveProcessado.query.order_by(
        RelatorioDriveProcessado.arquivo_modificado_em.desc(),
        RelatorioDriveProcessado.id.desc(),
    ).first()
    if ultimo is None:
        raise FileNotFoundError("Nenhum relatório foi processado.")

    total_sucessos = len(sucessos)

    return {
        "titulo": ultimo.titulo or "Resumo acumulado da automação SIEG",
        "executado_em": ultimo.executado_em or ultimo.arquivo_modificado_em,
        "resumo": {
            "certas": 0,
            "sucessos": total_sucessos,
            "ignorados": _inteiro_nao_negativo(ultimo.total_ignorados),
            "falhas": len(falhas),
        },
        "empresas_com_falha": [empresa.to_dict() for empresa in falhas],
        "empresas_com_sucesso": [empresa.to_dict() for empresa in sucessos],
        "arquivo_drive": {
            "id": ultimo.arquivo_id,
            "nome": ultimo.arquivo_nome,
            "modificado_em": ultimo.arquivo_modificado_em,
        },
        "historico": {
            "acumulado": True,
            "arquivos_processados": RelatorioDriveProcessado.query.count(),
            "empresas_acompanhadas": EmpresaRelatorio.query.count(),
        },
    }


def sincronizar_relatorios_drive():
    pasta_relatorios = os.getenv("GOOGLE_DRIVE_PASTA_RELATORIOS_ID")
    if not str(pasta_relatorios or "").strip():
        raise ValueError(
            "GOOGLE_DRIVE_PASTA_RELATORIOS_ID não foi configurado no arquivo .env."
        )

    drive = conectar_google_drive(_pasta_com_credenciais())
    arquivos = listar_relatorios_json(drive, pasta_relatorios)
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo JSON foi encontrado na pasta do Drive.")

    with _lock_acumulacao:
        arquivo = max(
            arquivos,
            key=lambda item: str(item.get("modifiedTime") or item.get("name") or ""),
        )
        dados = _normalizar_relatorio(ler_relatorio_json(drive, arquivo))
        db.session.query(EmpresaRelatorio).delete()
        db.session.query(RelatorioDriveProcessado).delete()
        db.session.commit()
        _acumular_relatorio(dados, arquivo)
        relatorio = _montar_relatorio_acumulado()
        if os.getenv("GOOGLE_DRIVE_PASTA_E_CNPJ_ID", "").strip():
            empresas_drive = listar_empresas_drive(drive)
            relatorio["empresas_com_sucesso"] = _sucessos_por_empresas_drive(
                empresas_drive,
                relatorio["empresas_com_falha"],
                relatorio["empresas_com_sucesso"],
            )
            total_sucessos = len(relatorio["empresas_com_sucesso"])
            relatorio["resumo"]["sucessos"] = total_sucessos
            relatorio["resumo"]["certas"] = total_sucessos
        return relatorio


@relatorio_bp.route("/relatorios/certificados-vencidos", methods=["GET"])
def relatorio_certificados_vencidos():
    try:
        return jsonify(sincronizar_relatorios_drive()), 200
    except FileNotFoundError as erro:
        return jsonify({"erro": str(erro)}), 404
    except (ValueError, json.JSONDecodeError) as erro:
        db.session.rollback()
        return jsonify({"erro": str(erro)}), 422
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao acumular relatórios de certificados")
        return jsonify({"erro": "Não foi possível ler o relatório no Google Drive."}), 502
