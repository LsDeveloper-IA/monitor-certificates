"""Regras de acesso compartilhadas pelas rotas locais do painel.

O painel pode rodar de duas formas:

- no modo de desenvolvimento, o Next encaminha as chamadas para o Flask;
- no pacote portatil, o proprio Flask serve o frontend estatico e recebe as
  chamadas diretamente do navegador em ``127.0.0.1``.

Em ambos os casos as requisicoes chegam de um endereco local. As rotas que
disparam automacoes ou alteram dados continuam exigindo uma chave, mas aceitam
tanto a chave interna usada pelas automacoes (``X-Automation-Key``) quanto a
chave administrativa digitada no painel (``X-Admin-Key``).
"""

from __future__ import annotations

import hmac
import os
from urllib.parse import urlparse

from flask import request


ENDERECOS_LOCAIS = {"127.0.0.1", "::1", "localhost"}
HOSTS_LOCAIS = {"127.0.0.1", "::1", "localhost"}


def _valor_configurado(nome: str) -> str:
    return os.getenv(nome, "").strip()


def _texto_igual(recebida: str, esperada: str) -> bool:
    if not recebida or not esperada:
        return False
    return hmac.compare_digest(recebida.encode("utf-8"), esperada.encode("utf-8"))


def requisicao_local() -> bool:
    """Indica se a requisicao veio da propria maquina."""
    return (request.remote_addr or "").strip() in ENDERECOS_LOCAIS


def origem_local_permitida() -> bool:
    """Aceita somente origens locais quando o navegador informa a origem.

    O cabecalho ``Origin`` e enviado pelo navegador em requisicoes POST/PUT e
    em preflights. Requisicoes internas (automacoes, curl e o proxy do Next)
    normalmente nao o enviam. Quando ele existe, precisa apontar para a propria
    maquina para evitar que uma pagina externa dispare acoes no painel local.
    """
    if request.headers.get("Sec-Fetch-Site", "").strip() == "cross-site":
        return False

    origem = (
        request.headers.get("Origin")
        or request.headers.get("Referer")
        or ""
    ).strip()
    if not origem:
        return True

    try:
        host = urlparse(origem).hostname
    except ValueError:
        return False
    return bool(host) and host.casefold() in HOSTS_LOCAIS


def chave_execucao_configurada() -> str:
    return _valor_configurado("AUTOMACAO_EXECUTION_KEY")


def chave_admin_configurada() -> str:
    return _valor_configurado("AUTOMACAO_ADMIN_KEY")


def chave_integracao_configurada() -> str:
    return _valor_configurado("INTEGRACAO_API_KEY")


def chave_execucao_valida() -> bool:
    return _texto_igual(
        request.headers.get("X-Automation-Key", "").strip(),
        chave_execucao_configurada(),
    )


def chave_admin_valida() -> bool:
    """Valida a chave administrativa do painel.

    Quando ``AUTOMACAO_ADMIN_KEY`` nao esta configurada, o token ``local``
    liberado pelo endpoint de configuracao inicial e aceito apenas para a
    propria maquina. Isso permite que o pacote portatil funcione sem exigir
    que o usuario digite uma chave, sem alterar o comportamento seguro dos
    testes e da instalacao em servidor.
    """
    recebida = request.headers.get("X-Admin-Key", "").strip()
    esperada = chave_admin_configurada()
    if esperada:
        return _texto_igual(recebida, esperada)
    return recebida == "local" and requisicao_local() and origem_local_permitida()


def chave_integracao_valida() -> bool:
    return _texto_igual(
        request.headers.get("X-API-Key", "").strip(),
        chave_integracao_configurada(),
    )


def acesso_administrativo_permitido() -> bool:
    """Regra das rotas de automacao, notificacao e WhatsContabil."""
    if not requisicao_local():
        return False
    return chave_execucao_valida() or chave_admin_valida()


def acesso_historico_permitido() -> bool:
    """Historico aceita a chave interna ou a chave do painel."""
    if not requisicao_local():
        return False
    return chave_execucao_valida() or chave_admin_valida()


def acesso_escrita_certificados_permitido() -> bool:
    """Escritas aceitam a chave de integracao ou o painel administrativo."""
    return chave_integracao_valida() or chave_admin_valida()
