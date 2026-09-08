import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

try:
    from integracoes.email_google import ErroEmailGoogle, enviar_email
except ModuleNotFoundError:  # Importacao pelos testes a partir da raiz do backend.
    from automation_engine.integracoes.email_google import (
        ErroEmailGoogle,
        enviar_email,
    )


VALORES_SIM = {"1", "s", "sim", "true"}


def _arquivo_historico():
    caminho = os.getenv("HISTORICO_RESUMO_ATUALIZACOES", "").strip()
    if caminho:
        return Path(caminho)
    return Path(__file__).resolve().parent.parent / "runtime" / "resumos_atualizacoes.json"


def listar_resumos_atualizacoes(limite=30):
    try:
        conteudo = json.loads(_arquivo_historico().read_text(encoding="utf-8"))
        if not isinstance(conteudo, list):
            return []
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return []
    return conteudo[: max(1, min(int(limite), 100))]


def _mascarar_email(valor):
    usuario, separador, dominio = str(valor or "").partition("@")
    if not separador:
        return "não configurado"
    prefixo = usuario[:2]
    return f"{prefixo}{'*' * max(3, len(usuario) - 2)}@{dominio}"


def _registrar_resumo(resultado, alteracoes, destinatario, origem):
    registro = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "executado_em": datetime.now().isoformat(),
        "origem": origem,
        "status": resultado.get("status"),
        "quantidade": len(alteracoes),
        "destinatario": _mascarar_email(destinatario),
        "erro": resultado.get("erro"),
        "alteracoes": alteracoes,
    }
    historico = listar_resumos_atualizacoes(100)
    historico.insert(0, registro)
    arquivo = _arquivo_historico()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(historico[:100], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporario, arquivo)
    return registro


def _formatar_data(valor):
    texto = str(valor or "").strip()
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return texto or "não informado"


def _formatar_cnpj(valor):
    numeros = re.sub(r"\D", "", str(valor or ""))
    if len(numeros) != 14:
        return str(valor or "não informado")
    return (
        f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/"
        f"{numeros[8:12]}-{numeros[12:]}"
    )


def montar_resumo_atualizacoes(alteracoes):
    """Monta um único e-mail interno com as mudanças da execução."""
    rotulos = {
        "novo": "Novo certificado",
        "renovado": "Certificado renovado",
        "vencimento_alterado": "Vencimento alterado",
    }
    assunto = f"Certificados atualizados na execução - {len(alteracoes)} empresa(s)"
    linhas = [
        "Olá,",
        "",
        "A automação identificou as seguintes alterações desde a execução anterior:",
        "",
    ]
    itens_html = []

    for alteracao in alteracoes:
        empresa = str(alteracao.get("empresa") or "Empresa não informada")
        cnpj = _formatar_cnpj(alteracao.get("cnpj"))
        tipo = rotulos.get(alteracao.get("tipo"), "Certificado atualizado")
        anterior = _formatar_data(alteracao.get("vencimento_anterior"))
        novo = _formatar_data(alteracao.get("vencimento_novo"))
        detalhe_data = f"Vencimento: {novo}"
        if alteracao.get("vencimento_anterior") and anterior != novo:
            detalhe_data = f"Vencimento: {anterior} → {novo}"

        linhas.extend([f"{empresa} ({cnpj})", f"{tipo} — {detalhe_data}", ""])
        itens_html.append(
            "<li style='margin-bottom:12px'>"
            f"<strong>{html.escape(empresa)}</strong> ({html.escape(cnpj)})<br>"
            f"{html.escape(tipo)} — {html.escape(detalhe_data)}"
            "</li>"
        )

    linhas.extend([
        "Este é um aviso automático do Monitor de Certificados Digitais.",
        "Nenhuma ação foi realizada no banco além da sincronização normal.",
    ])
    mensagem_html = (
        "<html><body><p>Olá,</p>"
        "<p>A automação identificou as seguintes alterações desde a execução "
        "anterior:</p><ul>"
        + "".join(itens_html)
        + "</ul><p><small>Este é um aviso automático do Monitor de "
        "Certificados Digitais.</small></p></body></html>"
    )
    return assunto, "\n".join(linhas), mensagem_html


def enviar_resumo_atualizacoes(resumo_sincronizacao, origem="automacao"):
    """Envia o resumo somente quando habilitado e houver mudança real."""
    alteracoes = resumo_sincronizacao.get("alteracoes_certificados") or []
    habilitado = os.getenv(
        "ENVIAR_RESUMO_ATUALIZACOES_AUTOMATICO", "nao"
    ).strip().casefold() in VALORES_SIM
    destinatario = os.getenv("EMAIL_RESUMO_ATUALIZACOES", "").strip()

    if not alteracoes:
        resultado = {"status": "sem_alteracoes", "quantidade": 0}
    elif not habilitado:
        resultado = {"status": "desativado", "quantidade": len(alteracoes)}
    elif not destinatario:
        resultado = {"status": "sem_destinatario", "quantidade": len(alteracoes)}
    else:
        resultado = None

    if resultado:
        try:
            resultado["registro"] = _registrar_resumo(
                resultado, alteracoes, destinatario, origem
            )
        except OSError:
            pass
        return resultado

    assunto, mensagem, mensagem_html = montar_resumo_atualizacoes(alteracoes)
    try:
        message_id = enviar_email(
            destinatario=destinatario,
            assunto=assunto,
            mensagem=mensagem,
            mensagem_html=mensagem_html,
        )
    except (ErroEmailGoogle, OSError) as erro:
        resultado = {
            "status": "falhou",
            "quantidade": len(alteracoes),
            "erro": str(erro),
        }
    else:
        resultado = {
            "status": "enviado",
            "quantidade": len(alteracoes),
            "message_id": message_id,
        }

    try:
        resultado["registro"] = _registrar_resumo(
            resultado, alteracoes, destinatario, origem
        )
    except OSError:
        pass
    return resultado
