"""Validacao local dos certificados .pfx antes de enviar ao portal."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.serialization import pkcs12

PREFIXO_SENHA = re.compile(r"^\s*senha\s*[-:=]\s*", re.IGNORECASE)


def variantes_senha(texto: str) -> list[str]:
    """Gera as formas em que a senha costuma aparecer nos arquivos do Drive."""
    if not texto:
        return []

    texto = texto.replace("\ufeff", "")
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    candidatos: list[str] = []

    def adicionar(valor: str) -> None:
        valor = valor.strip()
        if valor and valor not in candidatos:
            candidatos.append(valor)

    for base in (texto.strip(), linhas[0] if linhas else ""):
        if not base:
            continue
        adicionar(base)
        adicionar(PREFIXO_SENHA.sub("", base))
        adicionar(base.split(":")[-1] if ":" in base else "")
        adicionar(base.split("=")[-1] if "=" in base else "")

    apenas_ascii = texto.encode("ascii", errors="ignore").decode("ascii").strip()
    if apenas_ascii:
        adicionar(apenas_ascii)
        adicionar(PREFIXO_SENHA.sub("", apenas_ascii))

    # senhas padrao usadas pela contabilidade
    for padrao in ("123456", "12345678"):
        adicionar(padrao)

    return candidatos


@dataclass
class CertificadoValidado:
    caminho: Path
    senha: str
    titular_cnpj: str
    titular_nome: str
    valido_ate: datetime
    dias_restantes: int
    cnpj_confere: bool

    @property
    def expirado(self) -> bool:
        return self.valido_ate <= datetime.now(timezone.utc)


def _extrair_cnpj(subject: str) -> str:
    nome = _extrair_nome(subject)
    encontrados = re.findall(r"\d{14}", nome)
    if encontrados:
        return encontrados[0]
    encontrados = re.findall(r"\d{14}", subject)
    return encontrados[0] if encontrados else ""


def _extrair_nome(subject: str) -> str:
    for parte in subject.split(","):
        if parte.strip().upper().startswith("CN="):
            return parte.strip()[3:].split(":")[0].strip()
    return ""


def validar_pfx(
    caminho: str | Path,
    senhas: list[str],
    cnpj_esperado: str = "",
) -> CertificadoValidado | None:
    """Tenta abrir o .pfx. Devolve o certificado ou None se nenhuma senha servir."""
    caminho = Path(caminho)
    dados = caminho.read_bytes()

    for senha in senhas:
        try:
            _, certificado, _ = pkcs12.load_key_and_certificates(
                dados, senha.encode("utf-8")
            )
        except Exception:
            continue

        if certificado is None:
            continue

        try:
            valido_ate = certificado.not_valid_after_utc
        except AttributeError:  # cryptography < 42
            valido_ate = certificado.not_valid_after.replace(tzinfo=timezone.utc)

        agora = datetime.now(timezone.utc)
        dias = int((valido_ate - agora).total_seconds() // 86400)
        subject = certificado.subject.rfc4514_string()
        cnpj_titular = _extrair_cnpj(subject)
        cnpj_esperado = re.sub(r"\D", "", cnpj_esperado)

        return CertificadoValidado(
            caminho=caminho,
            senha=senha,
            titular_cnpj=cnpj_titular,
            titular_nome=_extrair_nome(subject),
            valido_ate=valido_ate,
            dias_restantes=dias,
            cnpj_confere=(not cnpj_esperado) or (cnpj_titular == cnpj_esperado),
        )

    return None
