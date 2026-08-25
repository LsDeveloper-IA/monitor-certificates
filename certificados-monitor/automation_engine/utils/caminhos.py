import sys
from pathlib import Path


def obter_pasta_aplicacao():
    """Retorna a pasta do projeto ou a pasta onde está o executável."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent
