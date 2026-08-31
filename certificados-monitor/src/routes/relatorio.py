import hashlib
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

from flask import Blueprint, current_app, jsonify
from sqlalchemy import func

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


def _chave_empresa(empresa):
    cnpj = re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
    if cnpj:
        return f"cnpj:{cnpj}"

    nome = unicodedata.normalize("NFKD", str(empresa.get("nome") or ""))
    nome = "".join(letra for letra in nome if not unicodedata.combining(letra))
    nome = re.sub(r"[^a-z0-9]+", " ", nome.casefold()).strip()
    return f"nome:{nome}" if nome else None


def _deduplicar_empresas(empresas):
    unicas = {}
    for empresa in empresas:
        if not isinstance(empresa, dict):
            continue
        chave = _chave_empresa(empresa)
        if chave:
            unicas[chave] = empresa
    return list(unicas.values())


def _chave_nome(empresa):
    nome = unicodedata.normalize("NFKD", str(empresa.get("nome") or ""))
    nome = "".join(letra for letra in nome if not unicodedata.combining(letra))
    return re.sub(r"[^a-z0-9]+", " ", nome.casefold()).strip()


def _sucessos_por_empresas_drive(empresas_drive, falhas, sucessos_explicitos):
    """No Drive, toda empresa sem falha Ã© considerada um sucesso."""
    nomes_com_falha = {_chave_nome(empresa) for empresa in falhas}
    nomes_com_falha.discard("")
    sucessos_por_nome = {
        _chave_nome(empresa): empresa
        for empresa in sucessos_explicitos
        if _chave_nome(empresa) and _chave_nome(empresa) not in nomes_com_falha
    }
    for empresa in empresas_drive:
        chave = _chave_nome(empresa)
        if chave and chave not in nomes_com_falha:
            sucessos_por_nome.setdefault(chave, empresa)
    return sorted(
        sucessos_por_nome.values(),
        key=lambda empresa: _chave_nome(empresa),
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
    resumo["sucessos"] = _inteiro_nao_negativo(
        resumo.get("certas", resumo.get("sucessos")),
        len(dados["empresas_com_sucesso"]),
    )
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

    maior_total_sucessos = db.session.query(
        func.max(RelatorioDriveProcessado.total_sucessos)
    ).scalar() or 0
    maior_total_ignorados = db.session.query(
        func.max(RelatorioDriveProcessado.total_ignorados)
    ).scalar() or 0
    total_sucessos = max(maior_total_sucessos, len(sucessos))

    return {
        "titulo": ultimo.titulo or "Resumo acumulado da automação SIEG",
        "executado_em": ultimo.executado_em or ultimo.arquivo_modificado_em,
        "resumo": {
            "certas": total_sucessos,
            "sucessos": total_sucessos,
            "ignorados": maior_total_ignorados,
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
        for arquivo in arquivos:
            chave = _chave_relatorio(arquivo)
            if RelatorioDriveProcessado.query.filter_by(chave=chave).first():
                continue
            dados = _normalizar_relatorio(ler_relatorio_json(drive, arquivo))
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
            relatorio["resumo"]["certas"] = total_sucessos
            relatorio["resumo"]["sucessos"] = total_sucessos
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
