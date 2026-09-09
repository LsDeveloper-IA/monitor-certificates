import os
from pathlib import Path

import _bootstrap
from sieg_comum.configuracao import ler_inteiro_nao_negativo


SCOPES = ["https://www.googleapis.com/auth/drive"]
TIME_CURTO = 1.5
TIME_LONGO = 6.0
TIME_FINAL = 15.0
MAX_TENTATIVAS_EXECUCAO = 3
ESPERA_ENTRE_TENTATIVAS = 30
SIMILARIDADE_MINIMA_PASTA = 0.85
PASTA_EXECUCAO = Path(__file__).resolve().parent
ARQUIVO_ENV = PASTA_EXECUCAO / ".env"
PASTA_REGISTROS = PASTA_EXECUCAO / "registros"
PASTA_ERROS = PASTA_REGISTROS / "erros"
ARQUIVO_CHECKPOINT = PASTA_REGISTROS / "checkpoint.json"
MIME_GOOGLE_DOC = "application/vnd.google-apps.document"


def carregar_arquivo_env():
    """Carrega SIEG_EMAIL e SIEG_SENHA do arquivo .env."""
    if not ARQUIVO_ENV.exists():
        return
    for linha in ARQUIVO_ENV.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        chave, separador, valor = linha.partition("=")
        if separador:
            os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


carregar_arquivo_env()


DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID", "").strip()
DRIVE_RELATORIOS_FOLDER_ID = os.getenv("DRIVE_RELATORIOS_FOLDER_ID", "").strip()
SIEG_SLOW_MO_MS = ler_inteiro_nao_negativo("SIEG_SLOW_MO_MS")
SIEG_UF_PADRAO = os.getenv("SIEG_UF_PADRAO", "").strip().upper()


def validar_pastas_drive():
    ausentes = [
        nome for nome, valor in (
            ("DRIVE_ROOT_FOLDER_ID", DRIVE_ROOT_FOLDER_ID),
            ("DRIVE_RELATORIOS_FOLDER_ID", DRIVE_RELATORIOS_FOLDER_ID),
        ) if not valor
    ]
    if ausentes:
        raise RuntimeError(
            f"Defina {', '.join(ausentes)} no arquivo {ARQUIVO_ENV}."
        )
