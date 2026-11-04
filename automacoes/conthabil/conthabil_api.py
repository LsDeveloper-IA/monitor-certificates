"""Cliente da API do portal Conthabil.

Endpoints usados:
  POST /auth/login/                         -> autentica e devolve o token JWT
  GET  /digital-certificates/?status=expired -> lista os certificados vencidos
  POST /digital-certificates/bulk-create/    -> importa varios .pfx de uma vez
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import requests

BASE_URL_PADRAO = "https://api.conthabilbr.com/api"


class ErroConthabil(RuntimeError):
    """Falha de comunicacao ou de regra de negocio do portal."""


@dataclass
class Certificado:
    id: str
    nome: str
    cnpj: str
    expira_em: str
    status: str

    @classmethod
    def de_json(cls, dados: dict) -> "Certificado":
        return cls(
            id=str(dados.get("id") or ""),
            nome=str(dados.get("name") or ""),
            cnpj="".join(ch for ch in str(dados.get("cnpj") or "") if ch.isdigit()),
            expira_em=str(dados.get("expires_at") or ""),
            status=str(dados.get("status") or ""),
        )


@dataclass
class ResultadoImportacao:
    total: int
    criados: list[dict]
    atualizados: list[dict]
    erros: list[dict]
    resumo: dict


class ClienteConthabil:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: int = 90,
    ) -> None:
        self.base_url = (base_url or os.getenv("CONTHABIL_API_URL") or BASE_URL_PADRAO).rstrip("/")
        self.timeout = timeout
        self.sessao = requests.Session()
        self.sessao.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://portal.conthabilbr.com",
                "Referer": "https://portal.conthabilbr.com/",
            }
        )
        if token:
            self.definir_token(token)

    # ------------------------------------------------------------------ auth
    def definir_token(self, token: str) -> None:
        self.sessao.headers["Authorization"] = f"JWT {token.strip()}"

    @property
    def token(self) -> str | None:
        auth = self.sessao.headers.get("Authorization", "")
        return auth[4:] if auth.startswith("JWT ") else None

    def login(self, identificador: str, senha: str) -> dict:
        """Autentica no portal. O campo aceita e-mail ou usuario."""
        resposta = self.sessao.post(
            f"{self.base_url}/auth/login/",
            data={"identificator": identificador, "password": senha},
            timeout=self.timeout,
        )
        if resposta.status_code in (400, 401, 403):
            raise ErroConthabil(
                "Credenciais invalidas no portal Conthabil "
                f"(HTTP {resposta.status_code})."
            )
        resposta.raise_for_status()
        dados = resposta.json()
        token = dados.get("token")
        if not token:
            raise ErroConthabil("O login nao retornou token JWT.")
        self.definir_token(token)
        return dados

    # ------------------------------------------------------------ consultas
    def dashboard(self) -> dict:
        resposta = self.sessao.get(
            f"{self.base_url}/digital-certificates/dashboard/", timeout=self.timeout
        )
        resposta.raise_for_status()
        return resposta.json()

    def listar_certificados(
        self, status: str | None = None, tamanho_pagina: int = 200
    ) -> list[Certificado]:
        itens: list[Certificado] = []
        offset = 0
        while True:
            params = {
                "ordering": "name",
                "limit": tamanho_pagina,
                "offset": offset,
            }
            if status:
                params["status"] = status
            resposta = self.sessao.get(
                f"{self.base_url}/digital-certificates/", params=params, timeout=self.timeout
            )
            resposta.raise_for_status()
            dados = resposta.json()
            lote = dados.get("results") or []
            itens.extend(Certificado.de_json(item) for item in lote)
            total = int(dados.get("count") or 0)
            offset += len(lote)
            if not lote or offset >= total:
                return itens

    def listar_vencidos(self) -> list[Certificado]:
        return self.listar_certificados(status="expired")

    # --------------------------------------------------------- importacao
    def importar(
        self,
        certificados: Sequence[tuple[Path, str]],
        timeout: int | None = None,
    ) -> ResultadoImportacao:
        """Envia varios (arquivo.pfx, senha) para o bulk-create do portal."""
        if not certificados:
            raise ValueError("Nenhum certificado para importar.")

        arquivos = []
        abertos = []
        try:
            for indice, (caminho, senha) in enumerate(certificados):
                caminho = Path(caminho)
                handle = caminho.open("rb")
                abertos.append(handle)
                arquivos.append(
                    (
                        f"certificates[{indice}].file",
                        (caminho.name, handle, "application/x-pkcs12"),
                    )
                )
                arquivos.append(
                    (f"certificates[{indice}].password", (None, senha))
                )

            resposta = self.sessao.post(
                f"{self.base_url}/digital-certificates/bulk-create/",
                files=arquivos,
                timeout=timeout or max(self.timeout, 300),
            )
        finally:
            for handle in abertos:
                handle.close()

        if resposta.status_code >= 400:
            raise ErroConthabil(
                f"Falha no upload (HTTP {resposta.status_code}): {resposta.text[:500]}"
            )

        dados = resposta.json()
        criados = dados.get("created") or []
        atualizados = dados.get("updated") or []
        erros = dados.get("errors") or []
        resumo = dados.get("summary") or {}
        return ResultadoImportacao(
            total=int(resumo.get("total") or len(certificados)),
            criados=criados,
            atualizados=atualizados,
            erros=erros,
            resumo=resumo,
        )

    def confirmar_atualizados(self, cnpjs: Iterable[str]) -> dict[str, str]:
        """Devolve {cnpj: expires_at} para os certificados informados."""
        alvos = {c for c in cnpjs}
        encontrados: dict[str, str] = {}
        for certificado in self.listar_certificados():
            if certificado.cnpj in alvos:
                encontrados[certificado.cnpj] = certificado.expira_em
                if len(encontrados) == len(alvos):
                    break
        return encontrados
