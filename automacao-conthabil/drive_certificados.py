"""Acesso ao Google Drive para localizar certificados e senhas.

Usa as credenciais OAuth (credentials.json + token.json) do projeto
monitor-certificates, que ja possui o escopo completo do Drive.
"""

from __future__ import annotations

import io
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

ESCOPO_LEITURA = "https://www.googleapis.com/auth/drive.readonly"
ESCOPO_COMPLETO = "https://www.googleapis.com/auth/drive"

MIME_PASTA = "application/vnd.google-apps.folder"
MIME_DOC_GOOGLE = "application/vnd.google-apps.document"


class ErroDrive(RuntimeError):
    """Falha ao acessar o Google Drive."""


@dataclass
class ItemDrive:
    id: str
    nome: str
    mime: str
    pais: list[str] = field(default_factory=list)
    subpasta: str = ""

    @property
    def eh_pasta(self) -> bool:
        return self.mime == MIME_PASTA

    @property
    def eh_certificado(self) -> bool:
        return Path(self.nome).suffix.lower() in (".pfx", ".p12")

    @property
    def eh_documento_senha(self) -> bool:
        return self.mime == MIME_DOC_GOOGLE and "senha" in self.nome.lower()

    @property
    def eh_texto_senha(self) -> bool:
        return self.mime.startswith("text/") and "senha" in self.nome.lower()


@dataclass
class PastaEmpresa:
    id: str
    nome: str
    itens: list[ItemDrive] = field(default_factory=list)

    @property
    def certificados(self) -> list[ItemDrive]:
        return [i for i in self.itens if i.eh_certificado]

    @property
    def senhas(self) -> list[ItemDrive]:
        return [i for i in self.itens if i.eh_documento_senha or i.eh_texto_senha]


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


class DriveCertificados:
    def __init__(
        self,
        pasta_credenciais: str | Path,
        pasta_raiz_id: str | None = None,
    ) -> None:
        self.pasta_credenciais = Path(pasta_credenciais)
        self.pasta_raiz_id = (
            pasta_raiz_id
            or os.getenv("GOOGLE_DRIVE_PASTA_E_CNPJ_ID")
            or "1XD29GlSrxVTGNZNB5SUanAK31ZZ7qWv4"
        )
        self._servico = None
        self._pastas: list[ItemDrive] | None = None
        self._conteudo_cache: dict[str, list[ItemDrive]] = {}

    # --------------------------------------------------------------- conexao
    @property
    def servico(self):
        if self._servico is None:
            self._servico = self._conectar()
        return self._servico

    def _conectar(self):
        arquivo_credenciais = self.pasta_credenciais / "credentials.json"
        arquivo_token = self.pasta_credenciais / "token.json"

        if not arquivo_token.exists():
            raise ErroDrive(
                f"token.json nao encontrado em {self.pasta_credenciais}.\n"
                "Copie credentials.json e token.json do projeto monitor-certificates "
                "ou gere um novo token."
            )

        credenciais = Credentials.from_authorized_user_file(str(arquivo_token))
        escopos = set(credenciais.scopes or [])
        if escopos and not escopos.intersection({ESCOPO_LEITURA, ESCOPO_COMPLETO}):
            raise ErroDrive("O token nao possui permissao de leitura do Drive.")

        if not credenciais.valid:
            if credenciais.expired and credenciais.refresh_token:
                credenciais.refresh(Request())
                arquivo_token.write_text(credenciais.to_json(), encoding="utf-8")
            elif arquivo_credenciais.exists():
                from google_auth_oauthlib.flow import InstalledAppFlow

                fluxo = InstalledAppFlow.from_client_secrets_file(
                    str(arquivo_credenciais), [ESCOPO_COMPLETO]
                )
                credenciais = fluxo.run_local_server(port=0)
                arquivo_token.write_text(credenciais.to_json(), encoding="utf-8")
            else:
                raise ErroDrive(
                    "Token expirado e credentials.json ausente. Nao foi possivel renovar."
                )

        return build("drive", "v3", credentials=credenciais, cache_discovery=False)

    # ---------------------------------------------------------------- listas
    def _listar(self, consulta: str) -> list[ItemDrive]:
        itens: list[ItemDrive] = []
        pagina = None
        while True:
            resultado = (
                self.servico.files()
                .list(
                    q=consulta,
                    pageSize=1000,
                    pageToken=pagina,
                    fields="nextPageToken, files(id, name, mimeType, parents)",
                    spaces="drive",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            for arquivo in resultado.get("files", []):
                itens.append(
                    ItemDrive(
                        id=arquivo["id"],
                        nome=arquivo.get("name", ""),
                        mime=arquivo.get("mimeType", ""),
                        pais=arquivo.get("parents", []),
                    )
                )
            pagina = resultado.get("nextPageToken")
            if not pagina:
                return itens

    def pastas_empresa(self) -> list[ItemDrive]:
        if self._pastas is None:
            self._pastas = [
                pasta
                for pasta in self._listar(
                    f"'{self.pasta_raiz_id}' in parents and "
                    f"mimeType = '{MIME_PASTA}' and trashed = false"
                )
                if pasta.nome.lower() != "desktop.ini"
            ]
        return self._pastas

    def conteudo_pasta(self, pasta_id: str, profundidade: int = 0) -> list[ItemDrive]:
        """Lista o conteudo da pasta e das subpastas (ate 4 niveis)."""
        if pasta_id in self._conteudo_cache:
            return self._conteudo_cache[pasta_id]

        itens = self._listar(f"'{pasta_id}' in parents and trashed = false")
        saida: list[ItemDrive] = []
        for item in itens:
            saida.append(item)
            if item.eh_pasta and profundidade < 4:
                for filho in self.conteudo_pasta(item.id, profundidade + 1):
                    filho.subpasta = f"{item.nome}/{filho.subpasta}".strip("/")
                    saida.append(filho)

        self._conteudo_cache[pasta_id] = saida
        return saida

    # -------------------------------------------------------------- busca
    def _pasta_por_cnpj(self, cnpj: str) -> ItemDrive | None:
        """Procura um arquivo com o CNPJ no nome e devolve a pasta dele."""
        consulta = (
            f"name contains '{cnpj}' and trashed = false and "
            f"mimeType != '{MIME_PASTA}'"
        )
        try:
            candidatos = self._listar(consulta)
        except Exception:
            return None

        pastas_por_id = {p.id: p for p in self.pastas_empresa()}
        for arquivo in candidatos:
            for pai in arquivo.pais:
                if pai in pastas_por_id:
                    return pastas_por_id[pai]

        # o arquivo pode estar em uma subpasta: sobe na arvore ate achar
        # a pasta da empresa (filha direta da pasta e-CNPJ)
        for arquivo in candidatos:
            atual = arquivo.pais[0] if arquivo.pais else None
            for _ in range(4):
                if not atual:
                    break
                if atual in pastas_por_id:
                    return pastas_por_id[atual]
                try:
                    meta = (
                        self.servico.files()
                        .get(fileId=atual, fields="id, name, parents", supportsAllDrives=True)
                        .execute()
                    )
                except Exception:
                    break
                atual = (meta.get("parents") or [None])[0]
        return None

    def localizar_pasta(self, cnpj: str, nome_empresa: str) -> ItemDrive | None:
        cnpj = somente_digitos(cnpj)
        alvo = normalizar(nome_empresa)

        pastas = self.pastas_empresa()

        # 1) nome da pasta exatamente igual ao nome da empresa
        for pasta in pastas:
            if normalizar(pasta.nome) == alvo:
                return pasta

        # 2) nome parecido E que contenha um .pfx com o CNPJ no nome
        candidatas = []
        for pasta in pastas:
            nome_pasta = normalizar(pasta.nome)
            if not nome_pasta or not alvo:
                continue
            if (nome_pasta in alvo or alvo in nome_pasta) and abs(
                len(nome_pasta) - len(alvo)
            ) <= 12:
                candidatas.append(pasta)
                try:
                    itens = self.conteudo_pasta(pasta.id)
                except Exception:
                    continue
                if any(
                    cnpj and cnpj in somente_digitos(item.nome)
                    for item in itens
                    if item.eh_certificado
                ):
                    return pasta

        # 3) busca direta pelo CNPJ no nome do arquivo
        por_cnpj = self._pasta_por_cnpj(cnpj)
        if por_cnpj is not None:
            return por_cnpj

        # 4) ultimo recurso: pasta com nome parecido
        return candidatas[0] if candidatas else None

    # ----------------------------------------------------------- downloads
    def baixar(self, item: ItemDrive) -> bytes:
        buffer = io.BytesIO()
        requisicao = self.servico.files().get_media(
            fileId=item.id, supportsAllDrives=True
        )
        baixador = MediaIoBaseDownload(buffer, requisicao)
        concluido = False
        while not concluido:
            _, concluido = baixador.next_chunk()
        return buffer.getvalue()

    def ler_texto(self, item: ItemDrive) -> str:
        if item.mime == MIME_DOC_GOOGLE:
            dados = (
                self.servico.files()
                .export(fileId=item.id, mimeType="text/plain")
                .execute()
            )
        else:
            dados = self.baixar(item)

        if isinstance(dados, bytes):
            for codificacao in ("utf-8", "latin-1"):
                try:
                    return dados.decode(codificacao)
                except UnicodeDecodeError:
                    continue
            return dados.decode("utf-8", errors="ignore")
        return str(dados)

    def ler_senhas(self, pasta: PastaEmpresa) -> list[str]:
        """Le todos os arquivos de senha da pasta e devolve os textos brutos."""
        textos: list[str] = []
        for item in pasta.senhas:
            try:
                textos.append(self.ler_texto(item))
            except Exception:
                continue
        return textos
