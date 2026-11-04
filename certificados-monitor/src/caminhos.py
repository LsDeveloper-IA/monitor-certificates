"""Caminhos compartilhados entre o backend e os dados locais.

Os dados gerados (banco, historicos, logs e segredos OAuth) ficam fora do
codigo, em ``storage/`` na raiz do repositorio. A variavel ``STORAGE_DIR``
permite apontar para outro local em producao. No executavel portatil, a pasta
de dados fica ao lado do ``.exe``.
"""

import os
import sys
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_REPOSITORIO = PASTA_BACKEND.parent


def pasta_aplicacao():
    """Retorna a raiz da aplicacao (repositorio ou pasta do executavel)."""
    configurada = os.getenv("MONITOR_APP_DIR", "").strip()
    if configurada:
        return Path(configurada).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return RAIZ_REPOSITORIO


def pasta_storage():
    """Retorna a pasta de dados gerados, criando-a quando necessario."""
    configurada = os.getenv("STORAGE_DIR", "").strip()
    if configurada:
        caminho = Path(configurada).expanduser()
        if not caminho.is_absolute():
            caminho = pasta_aplicacao() / caminho
        return caminho.resolve()

    if getattr(sys, "frozen", False):
        return pasta_aplicacao() / "storage"

    return RAIZ_REPOSITORIO / "storage"


def pasta_segredos(componente="backend"):
    """Retorna a pasta de credenciais/tokens de um componente."""
    return pasta_storage() / "secrets" / componente


def garantir_pasta(caminho):
    """Cria a pasta (e os pais) e devolve o caminho resolvido."""
    caminho = Path(caminho)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho
