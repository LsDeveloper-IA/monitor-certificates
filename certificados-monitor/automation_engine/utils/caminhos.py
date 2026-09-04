import sys
from pathlib import Path


def obter_pasta_aplicacao():
    """Retorna a pasta do projeto ou a pasta onde está o executável."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def obter_arquivo_env(pasta_aplicacao=None):
    """Localiza o .env do executável ou da raiz do backend integrado."""
    pasta = Path(pasta_aplicacao or obter_pasta_aplicacao()).resolve()
    arquivo_local = pasta / ".env"
    if arquivo_local.exists():
        return arquivo_local
    return pasta.parent / ".env"
