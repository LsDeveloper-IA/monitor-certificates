import hmac
import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from automation_engine.integracoes.whatscontabil import (
    ErroWhatsContabil,
    listar_conexoes,
    listar_templates,
    obter_conexao_oficial,
)


whatscontabil_bp = Blueprint("whatscontabil", __name__)
PASTA_BACKEND = Path(__file__).resolve().parents[2]


def _acesso_permitido():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return False
    esperada = os.getenv("AUTOMACAO_EXECUTION_KEY", "").strip()
    recebida = request.headers.get("X-Automation-Key", "").strip()
    return bool(esperada) and hmac.compare_digest(esperada, recebida)


@whatscontabil_bp.before_request
def proteger_integracao():
    if not _acesso_permitido():
        return jsonify({"erro": "Acesso nao autorizado"}), 401
    return None


def _configuracao_segura():
    numero = os.getenv("WHATSCONTABIL_NUMERO_TESTE", "").strip()
    numero_mascarado = f"***{numero[-4:]}" if numero else None
    return {
        "url_configurada": bool(os.getenv("WHATSCONTABIL_URL", "").strip()),
        "token_configurado": bool(os.getenv("WHATSCONTABIL_TOKEN", "").strip()),
        "modo": os.getenv("MODO_WHATSCONTABIL", "desativado").strip(),
        "numero_teste": numero_mascarado,
        "whatsapp_id": os.getenv("WHATSCONTABIL_WHATSAPP_ID", "").strip() or None,
    }


def _resumir_conexao(conexao):
    return {
        "id": conexao.get("id") or conexao.get("whatsappId"),
        "nome": conexao.get("name") or conexao.get("nome"),
        "status": conexao.get("status"),
        "oficial": conexao.get("isOfficial") in (1, True, "1"),
    }


@whatscontabil_bp.route("/whatscontabil/status", methods=["GET"])
def status_whatscontabil():
    return jsonify(_configuracao_segura()), 200


@whatscontabil_bp.route("/whatscontabil/validar", methods=["POST"])
def validar_whatscontabil():
    try:
        conexoes = listar_conexoes(PASTA_BACKEND)
        oficial = obter_conexao_oficial(conexoes)
        whatsapp_id = os.getenv("WHATSCONTABIL_WHATSAPP_ID", "").strip()
        templates = listar_templates(PASTA_BACKEND, whatsapp_id) if whatsapp_id else []
        return jsonify({
            **_configuracao_segura(),
            "conectado": True,
            "conexao": _resumir_conexao(oficial),
            "quantidade_conexoes": len(conexoes),
            "quantidade_templates": len(templates),
            "mensagem": "Integracao validada sem enviar mensagens.",
        }), 200
    except ErroWhatsContabil as erro:
        return jsonify({"erro": str(erro), **_configuracao_segura()}), 400
