import os
import sys
from pathlib import Path


def obter_pasta_aplicacao():
    """Retorna a pasta do projeto ou a pasta onde esta o executavel."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def obter_pasta_storage(pasta_aplicacao=None):
    """Retorna a raiz dos dados gerados (banco, logs, relatorios e segredos).

    Em desenvolvimento fica em ``storage/`` na raiz do repositorio. Em uma
    instalacao congelada, fica ao lado do executavel. ``STORAGE_DIR`` permite
    sobrescrever esse caminho.
    """
    configurada = os.getenv("STORAGE_DIR", "").strip()
    if configurada:
        caminho = Path(configurada).expanduser()
        if not caminho.is_absolute():
            base = Path(pasta_aplicacao or obter_pasta_aplicacao()).resolve()
            caminho = base / caminho
        return caminho.resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "storage"

    return Path(__file__).resolve().parents[3] / "storage"


def obter_pasta_segredos(componente="backend", pasta_aplicacao=None):
    """Retorna a pasta de credenciais e tokens de um componente."""
    return obter_pasta_storage(pasta_aplicacao) / "secrets" / componente


def obter_arquivo_env(pasta_aplicacao=None):
    """Localiza o .env do executavel ou da raiz do backend integrado."""
    pasta = Path(pasta_aplicacao or obter_pasta_aplicacao()).resolve()
    arquivo_local = pasta / ".env"
    if arquivo_local.exists():
        return arquivo_local
    return pasta.parent / ".env"
