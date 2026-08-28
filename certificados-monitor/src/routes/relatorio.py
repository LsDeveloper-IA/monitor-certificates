import json
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from automation_engine.integracoes.google_drive import (
    conectar_google_drive,
    ler_relatorio_json_mais_recente,
)

relatorio_bp = Blueprint("relatorio", __name__)


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
        if not isinstance(dados.get("resumo"), dict) or not isinstance(
            dados.get("empresas_com_falha"), list
        ):
            return jsonify({"erro": "O JSON do Drive não possui o formato esperado."}), 422
        return jsonify(dados), 200
    except FileNotFoundError as erro:
        return jsonify({"erro": str(erro)}), 404
    except (ValueError, json.JSONDecodeError) as erro:
        return jsonify({"erro": str(erro)}), 422
    except Exception:
        current_app.logger.exception("Falha ao ler o relatório de certificados no Drive")
        return jsonify({"erro": "Não foi possível ler o relatório no Google Drive."}), 502
