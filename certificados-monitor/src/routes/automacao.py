import hmac
import os
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from src.models.user import db
from src.services.executor_automacao import executor_automacao
from src.services.agendador_automacao import agendador_automacao


automacao_bp = Blueprint("automacao", __name__)
PASTA_BACKEND = Path(__file__).resolve().parents[2]


def _acesso_permitido():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return False
    esperada = os.getenv("AUTOMACAO_EXECUTION_KEY", "").strip()
    recebida = request.headers.get("X-Automation-Key", "").strip()
    return bool(esperada) and hmac.compare_digest(esperada, recebida)


@automacao_bp.before_request
def proteger_automacao():
    if not _acesso_permitido():
        return jsonify({"erro": "Acesso nao autorizado"}), 401
    return None


@automacao_bp.route("/automacao/status", methods=["GET"])
def status_automacao():
    return jsonify(executor_automacao.status()), 200


@automacao_bp.route("/automacao/historico", methods=["GET"])
def historico_automacao():
    return jsonify({"execucoes": executor_automacao.historico()}), 200


@automacao_bp.route("/automacao/agendador-status", methods=["GET"])
def status_agendador_automacao():
    return jsonify(agendador_automacao.status()), 200


@automacao_bp.route("/automacao/saude", methods=["GET"])
def saude_integracoes():
    integracoes = []

    try:
        db.session.execute(text("SELECT 1"))
        integracoes.append({
            "id": "backend",
            "nome": "Backend e banco do monitor",
            "estado": "ok",
            "detalhe": "API disponível e banco local respondendo.",
        })
    except Exception:
        integracoes.append({
            "id": "backend",
            "nome": "Backend e banco do monitor",
            "estado": "erro",
            "detalhe": "O banco local não respondeu à verificação.",
        })

    status_execucao = executor_automacao.status()
    dsn_configurado = bool(os.getenv("ODBC_DSN", "").strip())
    banco_estado = "ok" if dsn_configurado and status_execucao["estado"] == "concluida" else "configurado" if dsn_configurado else "atencao"
    banco_detalhe = (
        "DSN configurado e última automação concluída."
        if banco_estado == "ok"
        else "DSN configurado; a conexão será confirmada na próxima automação."
        if dsn_configurado
        else "ODBC_DSN não configurado."
    )
    integracoes.append({
        "id": "banco_clientes",
        "nome": "Banco de clientes",
        "estado": banco_estado,
        "detalhe": banco_detalhe,
    })

    pasta_certificados = os.getenv("PASTA_CERTIFICADOS", "").strip()
    pasta_disponivel = bool(pasta_certificados) and Path(pasta_certificados).exists()
    token_drive = (PASTA_BACKEND / "automation_engine" / "token.json").exists()
    credenciais_drive = (PASTA_BACKEND / "automation_engine" / "credentials.json").exists()
    drive_ok = pasta_disponivel and token_drive and credenciais_drive
    integracoes.append({
        "id": "google_drive",
        "nome": "Google Drive",
        "estado": "ok" if drive_ok else "atencao",
        "detalhe": (
            "Pasta local e credenciais de leitura disponíveis."
            if drive_ok
            else "Verifique a pasta sincronizada e os arquivos de autenticação."
        ),
    })

    whatsapp_configurado = all(
        os.getenv(chave, "").strip()
        for chave in (
            "WHATSCONTABIL_URL",
            "WHATSCONTABIL_TOKEN",
            "WHATSCONTABIL_WHATSAPP_ID",
        )
    )
    integracoes.append({
        "id": "whatscontabil",
        "nome": "WhatsContábil",
        "estado": "configurado" if whatsapp_configurado else "atencao",
        "detalhe": (
            "Configuração encontrada; a conexão externa é validada separadamente."
            if whatsapp_configurado
            else "Configuração incompleta no ambiente do backend."
        ),
    })

    template_configurado = bool(os.getenv("WHATSCONTABIL_TEMPLATE_TESTE", "").strip())
    integracoes.append({
        "id": "template",
        "nome": "Template de avisos aos clientes",
        "estado": "configurado" if template_configurado else "atencao",
        "detalhe": (
            "Nome configurado; confirme a aprovação na WhatsContábil."
            if template_configurado
            else "Nome do template aprovado ainda não configurado."
        ),
    })

    nome_template_equipe = os.getenv(
        "WHATSCONTABIL_TEMPLATE_EQUIPE_TESTE", ""
    ).strip()
    nome_template_equipe_documento = os.getenv(
        "WHATSCONTABIL_TEMPLATE_EQUIPE_DOCUMENTO_TESTE", ""
    ).strip()
    template_equipe_configurado = (
        nome_template_equipe_documento == "relatorio_pendencias_certificados"
        or nome_template_equipe == "resumo_pendencias_certificados"
    )
    integracoes.append({
        "id": "template_equipe",
        "nome": "Template interno da equipe",
        "estado": "configurado" if template_equipe_configurado else "atencao",
        "detalhe": (
            "Nome configurado; confirme a aprovação na WhatsContábil."
            if template_equipe_configurado
            else "Aguardando o template Utility consolidado da equipe."
        ),
    })

    nome_template_responsavel = os.getenv(
        "WHATSCONTABIL_TEMPLATE_RESPONSAVEL_TESTE", ""
    ).strip()
    nome_template_responsavel_documento = os.getenv(
        "WHATSCONTABIL_TEMPLATE_RESPONSAVEL_DOCUMENTO_TESTE", ""
    ).strip()
    template_responsavel_configurado = (
        nome_template_responsavel_documento
        == "relatorio_renovacoes_responsavel"
        or nome_template_responsavel == "resumo_renovacoes_responsavel"
    )
    integracoes.append({
        "id": "template_responsavel",
        "nome": "Template interno do responsável",
        "estado": "configurado" if template_responsavel_configurado else "atencao",
        "detalhe": (
            "Nome configurado; confirme a aprovação na WhatsContábil."
            if template_responsavel_configurado
            else "Aguardando o template Utility consolidado do responsável."
        ),
    })

    status_agendador = agendador_automacao.status()
    agendador_ok = status_agendador["ativo"] and status_agendador["monitorando"]
    integracoes.append({
        "id": "agendador",
        "nome": "Agendador",
        "estado": "ok" if agendador_ok else "atencao",
        "detalhe": (
            f"Ativo; próxima execução em {status_agendador['proxima_execucao']}."
            if agendador_ok
            else "Desativado ou sem monitor interno em execução."
        ),
    })

    return jsonify({
        "verificado_em": datetime.now().isoformat(),
        "integracoes": integracoes,
    }), 200


@automacao_bp.route("/automacao/agendador-configurar", methods=["POST"])
def configurar_agendador_automacao():
    dados = request.get_json(silent=True) or {}
    try:
        horarios = dados.get("horarios")
        if horarios is None:
            horarios = dados.get("horario", ["09:00", "14:00"])
        status = agendador_automacao.configurar(
            ativo=dados.get("ativo") is True,
            horarios=horarios,
            atualizar_excel=dados.get("atualizar_excel") is True,
            notificacoes_teste=dados.get("notificacoes_teste") is True,
        )
        return jsonify(
            {
                "mensagem": "Agendador atualizado com sucesso",
                "status": status,
            }
        ), 200
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400


@automacao_bp.route("/automacao/executar", methods=["POST"])
def executar_automacao():
    dados = request.get_json(silent=True) or {}
    try:
        executor_automacao.executar(
            atualizar_excel=dados.get("atualizar_excel") is True,
            notificacoes_teste=dados.get("notificacoes_teste") is True,
        )
        return jsonify(
            {
                "mensagem": "Automacao iniciada",
                "status": executor_automacao.status(),
            }
        ), 202
    except RuntimeError as erro:
        return jsonify({"erro": str(erro)}), 409
