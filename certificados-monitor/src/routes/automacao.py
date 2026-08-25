import hmac
import os

from flask import Blueprint, jsonify, request

from src.services.executor_automacao import executor_automacao


automacao_bp = Blueprint("automacao", __name__)


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


@automacao_bp.route("/automacao/executar", methods=["POST"])
def executar_automacao():
    dados = request.get_json(silent=True) or {}
    try:
        executor_automacao.executar(
            atualizar_excel=dados.get("atualizar_excel") is True,
        )
        return jsonify({"mensagem": "Automacao iniciada"}), 202
    except RuntimeError as erro:
        return jsonify({"erro": str(erro)}), 409
