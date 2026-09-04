import os
from pathlib import Path


SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_ROOT_FOLDER_ID = "1XD29GlSrxVTGNZNB5SUanAK31ZZ7qWv4"
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
DRIVE_RELATORIOS_FOLDER_ID = "1rEjYbkQE8YxJHFIAkrgEZfbLgenircff"


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
