"""Configuracao central do backend e validacao das variaveis de ambiente.

As automacoes continuam lendo os proprios ``.env``; este pacote concentra as
variaveis usadas pelo painel/API e falha cedo quando um valor invalido poderia
derrubar o processo em tempo de execucao.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path


RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]

_VERDADEIROS = {"1", "true", "sim", "s", "yes"}
_FALSOS = {"0", "false", "nao", "não", "n", "no"}
_SEGREDOS_PLACEHOLDER = {
    "",
    "altere-esta-chave-no-env",
    "gere-uma-chave-segura",
    "gere-outra-chave-interna-segura",
}
_URL = re.compile(r"^https?://[^\s/]+", re.IGNORECASE)


class ErroConfiguracao(ValueError):
    """Indica variaveis de ambiente ausentes ou invalidas."""


@dataclass(frozen=True)
class Configuracao:
    debug: bool
    host: str
    porta: int
    frontend_origem: str
    api_monitor_url: str
    secret_key: str
    integracao_api_key: str
    automacao_execution_key: str
    storage_dir: Path | None


def _texto(ambiente, nome, padrao=""):
    return str(ambiente.get(nome, padrao) or padrao).strip()


def _booleano(ambiente, nome, padrao, erros):
    valor = _texto(
        ambiente,
        nome,
        "sim" if padrao else "nao",
    ).casefold()
    if valor in _VERDADEIROS:
        return True
    if valor in _FALSOS:
        return False
    erros.append(
        f"{nome} deve ser booleano (sim/nao); valor recebido: {valor!r}."
    )
    return padrao


def _inteiro(ambiente, nome, padrao, minimo, maximo, erros):
    bruto = _texto(ambiente, nome, str(padrao))
    try:
        valor = int(bruto)
    except ValueError:
        erros.append(f"{nome} deve ser um numero inteiro; recebido: {bruto!r}.")
        return padrao
    if not minimo <= valor <= maximo:
        erros.append(f"{nome} deve estar entre {minimo} e {maximo}.")
    return valor


def _url(ambiente, nome, padrao, erros):
    valor = _texto(ambiente, nome, padrao).rstrip("/")
    if not _URL.match(valor):
        erros.append(f"{nome} deve comecar com http:// ou https://.")
    return valor


def _caminho(ambiente, nome, erros):
    valor = _texto(ambiente, nome)
    if not valor:
        return None
    caminho = Path(valor).expanduser()
    if not caminho.is_absolute():
        caminho = (RAIZ_REPOSITORIO / caminho).resolve()
    return caminho


def _segredo(ambiente, nome, padrao, exigir, erros):
    valor = _texto(ambiente, nome, padrao)
    if exigir and valor.casefold() in _SEGREDOS_PLACEHOLDER:
        erros.append(
            f"{nome} precisa ter um valor proprio quando "
            "MONITOR_CONFIG_STRICT=sim."
        )
    return valor


def carregar_configuracao(ambiente=None, exigir_segredos=None):
    """Le e valida as variaveis usadas pelo backend.

    ``ambiente`` permite testar com um dicionario sem alterar ``os.environ``.
    ``exigir_segredos`` forca a checagem das chaves internas; quando omitido,
    usa ``MONITOR_CONFIG_STRICT`` (padrao: desligado).
    """
    ambiente = os.environ if ambiente is None else ambiente
    erros = []

    exigir = (
        _booleano(ambiente, "MONITOR_CONFIG_STRICT", False, erros)
        if exigir_segredos is None
        else bool(exigir_segredos)
    )

    configuracao = Configuracao(
        debug=_booleano(ambiente, "FLASK_DEBUG", False, erros),
        host=_texto(ambiente, "FLASK_HOST", "127.0.0.1") or "127.0.0.1",
        porta=_inteiro(ambiente, "FLASK_PORT", 5000, 1, 65535, erros),
        frontend_origem=_url(
            ambiente,
            "FRONTEND_ORIGIN",
            "http://localhost:3000",
            erros,
        ),
        api_monitor_url=_url(
            ambiente,
            "API_MONITOR_URL",
            "http://localhost:5000",
            erros,
        ),
        secret_key=_segredo(
            ambiente,
            "SECRET_KEY",
            "altere-esta-chave-no-env",
            exigir,
            erros,
        ),
        integracao_api_key=_segredo(
            ambiente,
            "INTEGRACAO_API_KEY",
            "",
            exigir,
            erros,
        ),
        automacao_execution_key=_segredo(
            ambiente,
            "AUTOMACAO_EXECUTION_KEY",
            "",
            exigir,
            erros,
        ),
        storage_dir=_caminho(ambiente, "STORAGE_DIR", erros),
    )

    if erros:
        detalhes = "\n".join(f"- {erro}" for erro in erros)
        raise ErroConfiguracao(
            "Configuracao invalida. Corrija as variaveis abaixo:\n" + detalhes
        )
    return configuracao
