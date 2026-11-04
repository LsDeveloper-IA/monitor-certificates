"""Garante os caminhos de import ao rodar o pytest unico na raiz.

Cada automacao historicamente adiciona a propria pasta ao ``sys.path``. Em uma
execucao unica, ``automacoes/sieg`` precisa vir primeiro para que ``import
config`` continue resolvendo ``automacoes/sieg/config.py`` (e nao o pacote
``config/`` da raiz).
"""

import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parent

CAMINHOS = (
    RAIZ / "certificados-monitor",
    RAIZ / "automacoes",
    RAIZ / "automacoes" / "sieg_comum",
)

for caminho in CAMINHOS:
    texto = str(caminho)
    if texto not in sys.path:
        sys.path.insert(0, texto)

CAMINHO_SIEG = str(RAIZ / "automacoes" / "sieg")
if CAMINHO_SIEG in sys.path:
    sys.path.remove(CAMINHO_SIEG)
sys.path.insert(0, CAMINHO_SIEG)
