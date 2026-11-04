"""Configuracao inicial do painel executado na propria maquina.

O frontend portatil consulta este endpoint ao abrir para preencher a chave
administrativa automaticamente. A resposta so e entregue para requisicoes
locais e com origem local; uma pagina externa nao consegue ler a chave.
"""

from flask import Blueprint, jsonify

from src.seguranca import (
    chave_admin_configurada,
    origem_local_permitida,
    requisicao_local,
)


configuracao_local_bp = Blueprint("configuracao_local", __name__)


@configuracao_local_bp.route("/configuracao/chave-admin", methods=["GET"])
def chave_admin_local():
    if not requisicao_local() or not origem_local_permitida():
        return jsonify({"erro": "Acesso nao autorizado"}), 403

    chave = chave_admin_configurada()
    return jsonify({
        "chave": chave or "local",
        "protegida": bool(chave),
    }), 200
