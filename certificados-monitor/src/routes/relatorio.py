import json
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from automation_engine.integracoes.google_drive import (
    conectar_google_drive,
    ler_relatorio_json_mais_recente,
)

relatorio_bp = Blueprint("relatorio", __name__)


def _normalizar_relatorio(dados):
    resumo = dados.get("resumo")
    falhas = dados.get("empresas_com_falha")
    if not isinstance(resumo, dict) or not isinstance(falhas, list):
        raise ValueError("O JSON do Drive não possui o formato esperado.")

    nomes_listas_sucesso = (
        "empresas_com_sucesso",
        "empresas_certas",
        "empresas_corretas",
    )
    sucessos = next(
        (
            dados[nome]
            for nome in nomes_listas_sucesso
            if isinstance(dados.get(nome), list)
        ),
        [],
    )

    # A automação SIEG atual chama o total de sucessos de "certas". A API
    # expõe também o nome canônico "sucessos" para manter o frontend simples.
    total_sucessos = resumo.get("certas", resumo.get("sucessos", len(sucessos)))
    resumo["sucessos"] = total_sucessos
    dados["empresas_com_sucesso"] = sucessos
    return dados


def _pasta_com_credenciais():
    configurada = os.getenv("GOOGLE_DRIVE_CREDENCIAIS_DIR", "").strip()
    if configurada:
        return Path(configurada)
    raiz = Path(__file__).resolve().parents[2]
    return next(
        (pasta for pasta in (raiz, raiz.parent) if (pasta / "credentials.json").exists()),
        raiz,
    )


@relatorio_bp.route("/relatorios/certificados-vencidos", methods=["GET"])
def relatorio_certificados_vencidos():
    try:
        pasta_relatorios = os.getenv("GOOGLE_DRIVE_PASTA_RELATORIOS_ID")
        if not str(pasta_relatorios or "").strip():
            raise ValueError(
                "GOOGLE_DRIVE_PASTA_RELATORIOS_ID não foi configurado no arquivo .env."
            )
        drive = conectar_google_drive(_pasta_com_credenciais())
        dados = ler_relatorio_json_mais_recente(
            drive, pasta_relatorios
        )
        return jsonify(_normalizar_relatorio(dados)), 200
    except FileNotFoundError as erro:
        return jsonify({"erro": str(erro)}), 404
    except (ValueError, json.JSONDecodeError) as erro:
        return jsonify({"erro": str(erro)}), 422
    except Exception:
        current_app.logger.exception("Falha ao ler o relatório de certificados no Drive")
        return jsonify({"erro": "Não foi possível ler o relatório no Google Drive."}), 502
