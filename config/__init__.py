"""Validacao compartilhada das variaveis de ambiente do painel."""

from .validacao import (
    Configuracao,
    ErroConfiguracao,
    RAIZ_REPOSITORIO,
    carregar_configuracao,
)

__all__ = [
    "Configuracao",
    "ErroConfiguracao",
    "RAIZ_REPOSITORIO",
    "carregar_configuracao",
]
