"""Caminhos compartilhados entre o backend e os dados locais.

Os dados gerados (banco, historicos, logs e segredos OAuth) ficam fora do
codigo, em ``storage/`` na raiz do repositorio. A variavel ``STORAGE_DIR``
permite apontar para outro local em producao.
"""

import os
from pathlib import Path


PASTA_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_REPOSITORIO = PASTA_BACKEND.parent


def pasta_storage():
    """Retorna a pasta de dados gerados, criando-a quando necessario."""
    configurada = os.getenv("STORAGE_DIR", "").strip()
    if configurada:
        caminho = Path(configurada).expanduser()
        if not caminho.is_absolute():
            caminho = PASTA_BACKEND / caminho
        return caminho.resolve()

    return RAIZ_REPOSITORIO / "storage"


def pasta_segredos(componente="backend"):
    """Retorna a pasta de credenciais/tokens de um componente."""
    return pasta_storage() / "secrets" / componente


def garantir_pasta(caminho):
    """Cria a pasta (e os pais) e devolve o caminho resolvido."""
    caminho = Path(caminho)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho
