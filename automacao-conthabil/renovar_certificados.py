"""Renovador automatico de certificados digitais no portal Conthabil.

Fluxo:
  1. autentica no portal
  2. lista os certificados vencidos
  3. localiza o .pfx e a senha na pasta do Google Drive (e-CNPJ)
  4. valida localmente (senha, CNPJ e data de validade)
  5. envia os validos para o portal (bulk-create)
  6. confirma na API e grava o relatorio
"""

from __future__ import annotations

import argparse
import csv
import getpass
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from conthabil_api import Certificado, ClienteConthabil, ErroConthabil
from drive_certificados import DriveCertificados, ErroDrive, PastaEmpresa
from validacao import CertificadoValidado, validar_pfx, variantes_senha

STATUS = {
    "IMPORTADO": "Importado com sucesso",
    "VENCIDO_DRIVE": "Arquivo do Drive ja esta vencido",
    "SEM_ARQUIVO": "Sem arquivo .pfx na pasta do Drive",
    "SENHA_NAO_ENCONTRADA": "Nao consegui abrir o .pfx (senha)",
    "CNPJ_DIVERGENTE": "Certificado pertence a outro CNPJ",
    "ERRO_PORTAL": "Portal recusou a importacao",
    "ERRO_DRIVE": "Erro ao acessar o Drive",
    "PARCIAL": "Importado, mas nao confirmado na API",
}

PASTAS_PADRAO = {
    "drive": "1XD29GlSrxVTGNZNB5SUanAK31ZZ7qWv4",
}


def pasta_aplicacao() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _vigente(data_iso: str) -> bool:
    """True se a data ISO informada ainda nao passou."""
    if not data_iso:
        return False
    texto = data_iso.replace("Z", "+00:00")
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return False
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data > datetime.now(timezone.utc)


def carregar_config(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not caminho.exists():
        return valores
    for linha in caminho.read_text(encoding="utf-8", errors="ignore").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


@dataclass
class ResultadoEmpresa:
    cnpj: str
    empresa: str
    status: str
    detalhe: str = ""
    arquivo: str = ""
    valido_ate: str = ""
    novo_vencimento: str = ""


@dataclass
class ResultadoExecucao:
    total_vencidos: int = 0
    resultados: list[ResultadoEmpresa] = field(default_factory=list)
    iniciado_em: str = ""
    finalizado_em: str = ""
    pasta_relatorio: str = ""

    def contar(self, status: str) -> int:
        return sum(1 for r in self.resultados if r.status == status)

    @property
    def importados(self) -> int:
        return self.contar("IMPORTADO") + self.contar("PARCIAL")


class Renovador:
    def __init__(
        self,
        cliente: ClienteConthabil,
        drive: DriveCertificados,
        pasta_dados: Path,
        log: Callable[[str], None] = print,
    ) -> None:
        self.cliente = cliente
        self.drive = drive
        self.pasta_dados = pasta_dados
        self.log = log
        self.execucao = ResultadoExecucao()

    # -------------------------------------------------------------- execucao
    def executar(
        self,
        simular: bool = False,
        limite: int | None = None,
        cnpjs: list[str] | None = None,
        tamanho_lote: int = 10,
        confirmar_final: bool = True,
    ) -> ResultadoExecucao:
        inicio = datetime.now()
        self.execucao.iniciado_em = inicio.strftime("%d/%m/%Y %H:%M:%S")
        pasta_execucao = self.pasta_dados / inicio.strftime("%Y-%m-%d_%H-%M-%S")
        pasta_execucao.mkdir(parents=True, exist_ok=True)

        self.log("Consultando certificados vencidos no portal...")
        vencidos = self.cliente.listar_vencidos()
        if cnpjs:
            alvo = {re.sub(r"\D", "", c) for c in cnpjs}
            vencidos = [c for c in vencidos if c.cnpj in alvo]
        if limite:
            vencidos = vencidos[:limite]

        self.execucao.total_vencidos = len(vencidos)
        self.log(f"Certificados vencidos encontrados: {len(vencidos)}")
        if not vencidos:
            self.execucao.finalizado_em = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            return self.execucao

        self.log("Indexando pastas do Google Drive...")
        try:
            total_pastas = len(self.drive.pastas_empresa())
            self.log(f"Pastas de empresas no Drive: {total_pastas}")
        except Exception as erro:
            self.log(f"AVISO: nao consegui listar as pastas do Drive: {erro}")

        validos: list[_ValidadoComResultado] = []
        por_cnpj: dict[str, ResultadoEmpresa] = {}

        for indice, certificado in enumerate(vencidos, start=1):
            rotulo = f"[{indice}/{len(vencidos)}] {certificado.nome} ({certificado.cnpj})"
            self.log(rotulo)
            resultado, validado = self._processar_empresa(certificado, pasta_execucao)
            self.execucao.resultados.append(resultado)
            por_cnpj[resultado.cnpj] = resultado

            if resultado.status == "PRONTO" and validado is not None:
                self.log(f"    -> valido ate {resultado.valido_ate}, sera importado")
                validos.append(
                    _ValidadoComResultado(
                        caminho=validado.caminho,
                        senha=validado.senha,
                        cnpj=certificado.cnpj,
                        resultado=resultado,
                    )
                )
            else:
                self.log(f"    -> {STATUS.get(resultado.status, resultado.status)}: {resultado.detalhe}")

        if not validos:
            self.log("Nenhum certificado valido para importar.")
        elif simular:
            self.log(f"SIMULACAO: {len(validos)} certificado(s) seriam importados.")
            for item in validos:
                item.resultado.status = "SIMULADO"
                item.resultado.detalhe = "Simulacao - nao enviado ao portal"
        else:
            self._importar_em_lotes(validos, tamanho_lote, por_cnpj)
            if confirmar_final:
                self._confirmar(por_cnpj)

        self.execucao.finalizado_em = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.execucao.pasta_relatorio = str(self._gravar_relatorio(pasta_execucao))
        return self.execucao

    # ---------------------------------------------------------------- etapas
    def _processar_empresa(
        self, certificado: Certificado, pasta_execucao: Path
    ) -> tuple[ResultadoEmpresa, CertificadoValidado | None]:
        resultado = ResultadoEmpresa(
            cnpj=certificado.cnpj, empresa=certificado.nome, status=""
        )
        try:
            pasta = self.drive.localizar_pasta(certificado.cnpj, certificado.nome)
        except Exception as erro:
            resultado.status = "ERRO_DRIVE"
            resultado.detalhe = str(erro)[:200]
            return resultado, None

        if pasta is None:
            resultado.status = "SEM_ARQUIVO"
            resultado.detalhe = "Pasta da empresa nao encontrada no Drive"
            return resultado, None

        try:
            itens = self.drive.conteudo_pasta(pasta.id)
        except Exception as erro:
            resultado.status = "ERRO_DRIVE"
            resultado.detalhe = str(erro)[:200]
            return resultado, None

        empresa = PastaEmpresa(id=pasta.id, nome=pasta.nome, itens=itens)
        arquivos = empresa.certificados
        if not arquivos:
            resultado.status = "SEM_ARQUIVO"
            resultado.detalhe = f"Pasta '{pasta.nome}' sem .pfx/.p12"
            return resultado, None

        textos = self.drive.ler_senhas(empresa)
        senhas: list[str] = []
        for texto in textos:
            senhas.extend(variantes_senha(texto))
        if not senhas:
            senhas = ["123456", "12345678"]

        melhor: CertificadoValidado | None = None
        divergente: CertificadoValidado | None = None
        vencido: CertificadoValidado | None = None
        pasta_empresa = pasta_execucao / re.sub(r"\W+", "_", certificado.nome)[:40]
        pasta_empresa.mkdir(parents=True, exist_ok=True)

        for indice, item in enumerate(arquivos):
            destino = pasta_empresa / f"{certificado.cnpj}__{indice}{Path(item.nome).suffix.lower()}"
            try:
                destino.write_bytes(self.drive.baixar(item))
            except Exception:
                continue

            validado = validar_pfx(destino, senhas, certificado.cnpj)
            if validado is None:
                continue
            if not validado.cnpj_confere:
                divergente = validado
                continue
            if validado.expirado:
                if vencido is None or validado.valido_ate > vencido.valido_ate:
                    vencido = validado
                continue
            if melhor is None or validado.valido_ate > melhor.valido_ate:
                melhor = validado

        if melhor is not None:
            resultado.status = "PRONTO"
            resultado.detalhe = "Certificado valido encontrado no Drive"
            resultado.arquivo = str(melhor.caminho)
            resultado.valido_ate = melhor.valido_ate.strftime("%d/%m/%Y")
            return resultado, melhor

        if vencido is not None:
            resultado.status = "VENCIDO_DRIVE"
            resultado.valido_ate = vencido.valido_ate.strftime("%d/%m/%Y")
            resultado.arquivo = str(vencido.caminho)
            resultado.detalhe = (
                f"Certificado do Drive venceu em {resultado.valido_ate}; "
                "coloque o arquivo renovado na pasta"
            )
            return resultado, None

        if divergente is not None:
            resultado.status = "CNPJ_DIVERGENTE"
            resultado.detalhe = (
                f"Certificado pertence ao CNPJ {divergente.titular_cnpj} "
                f"({divergente.titular_nome})"
            )
            return resultado, None

        resultado.status = "SENHA_NAO_ENCONTRADA"
        resultado.detalhe = (
            f"{len(arquivos)} arquivo(s) encontrados, nenhuma senha abriu o certificado"
        )
        return resultado, None

    def _importar_em_lotes(
        self,
        validos: list["_ValidadoComResultado"],
        tamanho_lote: int,
        por_cnpj: dict[str, ResultadoEmpresa],
    ) -> None:
        total_lotes = (len(validos) + tamanho_lote - 1) // tamanho_lote
        for numero in range(total_lotes):
            lote = validos[numero * tamanho_lote : (numero + 1) * tamanho_lote]
            self.log(
                f"Importando lote {numero + 1}/{total_lotes} "
                f"({len(lote)} certificado(s))..."
            )
            try:
                resposta = self.cliente.importar(
                    [(item.caminho, item.senha) for item in lote]
                )
            except Exception as erro:
                for item in lote:
                    item.resultado.status = "ERRO_PORTAL"
                    item.resultado.detalhe = str(erro)[:200]
                continue

            atualizados = {int(i.get("index", -1)) for i in resposta.atualizados}
            criados = {int(i.get("index", -1)) for i in resposta.criados}
            for indice, item in enumerate(lote):
                if indice in atualizados or indice in criados:
                    item.resultado.status = "IMPORTADO"
                    item.resultado.detalhe = "Atualizado no portal"
                else:
                    item.resultado.status = "ERRO_PORTAL"

            for erro in resposta.erros:
                indice = int(erro.get("index", -1))
                if 0 <= indice < len(lote):
                    mensagem = erro.get("errors") or {}
                    if isinstance(mensagem, dict):
                        texto = "; ".join(
                            str(v) for valor in mensagem.values() for v in (
                                valor if isinstance(valor, list) else [valor]
                            )
                        )
                    else:
                        texto = str(mensagem)
                    lote[indice].resultado.status = "ERRO_PORTAL"
                    lote[indice].resultado.detalhe = texto[:200]

    def _confirmar(self, por_cnpj: dict[str, ResultadoEmpresa]) -> None:
        pendentes = {
            cnpj
            for cnpj, resultado in por_cnpj.items()
            if resultado.status == "IMPORTADO"
        }
        if not pendentes:
            return
        self.log(f"Conferindo {len(pendentes)} importacao(oes) na API...")
        try:
            novos = self.cliente.confirmar_atualizados(pendentes)
        except Exception as erro:
            self.log(f"AVISO: falha ao confirmar na API: {erro}")
            return
        for cnpj in pendentes:
            resultado = por_cnpj[cnpj]
            if cnpj in novos:
                resultado.novo_vencimento = novos[cnpj]
                if _vigente(novos[cnpj]):
                    continue
                resultado.status = "ERRO_PORTAL"
                resultado.detalhe = (
                    "O portal respondeu OK, mas o certificado continua vencido"
                )
            else:
                resultado.status = "PARCIAL"
                resultado.detalhe = (
                    "O portal respondeu OK, mas o certificado nao foi localizado "
                    "na listagem"
                )

    # ------------------------------------------------------------- relatorio
    def _gravar_relatorio(self, pasta_execucao: Path) -> Path:
        caminho_csv = pasta_execucao / "resultado.csv"
        with caminho_csv.open("w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(
                [
                    "CNPJ",
                    "Empresa",
                    "Situacao",
                    "Detalhe",
                    "Valido ate (arquivo)",
                    "Novo vencimento (portal)",
                ]
            )
            for resultado in self.execucao.resultados:
                escritor.writerow(
                    [
                        resultado.cnpj,
                        resultado.empresa,
                        resultado.status,
                        resultado.detalhe,
                        resultado.valido_ate,
                        resultado.novo_vencimento,
                    ]
                )

        linhas = [
            "# Resultado da automacao - Certificados Conthabil",
            "",
            f"Inicio: {self.execucao.iniciado_em}",
            f"Fim: {self.execucao.finalizado_em}",
            f"Vencidos analisados: {self.execucao.total_vencidos}",
            "",
            "| Situacao | Quantidade |",
            "|---|---|",
        ]
        for status in list(STATUS) + ["SIMULADO"]:
            quantidade = self.execucao.contar(status)
            if quantidade:
                linhas.append(f"| {STATUS.get(status, status)} | {quantidade} |")

        linhas += [
            "",
            "## Detalhe por empresa",
            "",
            "| CNPJ | Empresa | Situacao | Detalhe |",
            "|---|---|---|---|",
        ]
        for resultado in self.execucao.resultados:
            detalhe = (
                resultado.detalhe
                if resultado.status != "PRONTO"
                else f"valido ate {resultado.valido_ate}"
            )
            linhas.append(
                f"| {resultado.cnpj} | {resultado.empresa} | "
                f"{STATUS.get(resultado.status, resultado.status)} | {detalhe} |"
            )

        caminho_md = pasta_execucao / "resultado.md"
        caminho_md.write_text("\n".join(linhas), encoding="utf-8")
        return caminho_md


@dataclass
class _ValidadoComResultado:
    caminho: Path
    senha: str
    cnpj: str
    resultado: ResultadoEmpresa


# --------------------------------------------------------------------- CLI
def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Renova os certificados digitais vencidos no portal Conthabil."
    )
    parser.add_argument("--simular", action="store_true", help="Nao envia nada ao portal")
    parser.add_argument("--limite", type=int, help="Processa no maximo N empresas")
    parser.add_argument("--cnpj", help="Lista de CNPJs separados por virgula")
    parser.add_argument("--lote", type=int, default=10, help="Certificados por envio")
    parser.add_argument("--token", help="Token JWT ja existente (dispensa login)")
    parser.add_argument("--email", help="E-mail ou usuario do portal")
    parser.add_argument("--senha", help="Senha do portal")
    parser.add_argument("--pasta-drive", help="ID da pasta e-CNPJ no Google Drive")
    parser.add_argument("--saida", help="Pasta para downloads e relatorios")
    parser.add_argument("--sem-confirmar", action="store_true", help="Nao confere na API")
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = montar_parser().parse_args(argv)
    base = pasta_aplicacao()
    config = carregar_config(base / "config.env")

    def cfg(chave: str, padrao: str = "") -> str:
        return os.getenv(chave) or config.get(chave) or padrao

    pasta_dados = Path(argumentos.saida) if argumentos.saida else base / "dados"
    pasta_dados.mkdir(parents=True, exist_ok=True)

    try:
        cliente = ClienteConthabil()
        token = argumentos.token or cfg("CONTHABIL_TOKEN")
        if token:
            cliente.definir_token(token)
            print("Usando token informado.")
        else:
            email = argumentos.email or cfg("CONTHABIL_EMAIL")
            senha = argumentos.senha or cfg("CONTHABIL_SENHA")
            if not email:
                email = input("E-mail/usuario do portal Conthabil: ").strip()
            if not senha:
                senha = getpass.getpass("Senha do portal: ")
            print("Autenticando no portal...")
            cliente.login(email, senha)

        pasta_credenciais = Path(
            cfg("GOOGLE_DRIVE_CREDENCIAIS_DIR", str(base / "credenciais"))
        )
        if not pasta_credenciais.is_absolute():
            pasta_credenciais = base / pasta_credenciais

        drive = DriveCertificados(
            pasta_credenciais,
            argumentos.pasta_drive or cfg("GOOGLE_DRIVE_PASTA_E_CNPJ_ID", PASTAS_PADRAO["drive"]),
        )

        renovador = Renovador(cliente, drive, pasta_dados, print)
        cnpjs = argumentos.cnpj.split(",") if argumentos.cnpj else None
        resultado = renovador.executar(
            simular=argumentos.simular,
            limite=argumentos.limite,
            cnpjs=cnpjs,
            tamanho_lote=max(1, argumentos.lote),
            confirmar_final=not argumentos.sem_confirmar,
        )
    except (ErroConthabil, ErroDrive) as erro:
        print(f"ERRO: {erro}")
        return 2
    except KeyboardInterrupt:
        print("\nCancelado pelo usuario.")
        return 130
    except Exception as erro:  # noqa: BLE001 - mensagem amigavel no console
        print(f"ERRO inesperado: {erro}")
        return 3

    print()
    print("=" * 60)
    print(f"Vencidos analisados ....: {resultado.total_vencidos}")
    print(f"Importados com sucesso .: {resultado.importados}")
    for status, texto in STATUS.items():
        quantidade = resultado.contar(status)
        if quantidade and status != "IMPORTADO":
            print(f"{texto:<24}: {quantidade}")
    print(f"Relatorio ..............: {resultado.pasta_relatorio}")
    print("=" * 60)
    return 0 if resultado.importados or resultado.total_vencidos == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
