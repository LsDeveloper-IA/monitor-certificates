"""Executa a renovacao de certificados no portal Conthabil.

Este ponto de entrada substitui o antigo executavel/interface grafica: a
automacao roda em segundo plano e envia o andamento para a saida padrao, que e
acompanhada pelo painel web junto das demais automacoes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from conthabil_api import ClienteConthabil, ErroConthabil
from drive_certificados import DriveCertificados, ErroDrive
from renovar_certificados import PASTAS_PADRAO, STATUS, Renovador


def carregar_arquivo_env() -> None:
    """Carrega o .env local sem substituir valores ja definidos no ambiente."""
    arquivo_env = BASE / ".env"
    if not arquivo_env.exists():
        return

    for linha in arquivo_env.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        linha = linha.removeprefix("$env:")
        nome, valor = linha.split("=", 1)
        os.environ.setdefault(nome.strip(), valor.strip().strip("\"'"))


def registrar(mensagem: str) -> None:
    print(str(mensagem).rstrip(), flush=True)


def pasta_credenciais_drive() -> Path:
    """Usa a pasta configurada ou reaproveita as credenciais do repositorio."""
    configurada = os.getenv("GOOGLE_DRIVE_CREDENCIAIS_DIR", "").strip()
    if configurada:
        pasta = Path(configurada)
        return pasta if pasta.is_absolute() else BASE / pasta

    for candidata in (BASE / "credenciais", RAIZ):
        if (candidata / "token.json").exists():
            return candidata

    return BASE / "credenciais"


def pasta_de_dados() -> Path:
    configurada = os.getenv("CONTHABIL_SAIDA", "").strip()
    if not configurada:
        return BASE / "dados"
    pasta = Path(configurada)
    return pasta if pasta.is_absolute() else BASE / pasta


def ler_inteiro(nome: str, padrao: int) -> int:
    valor = os.getenv(nome, str(padrao)).strip()
    try:
        return max(1, int(valor))
    except ValueError:
        registrar(f"AVISO: {nome} invalido ({valor!r}); usando {padrao}.")
        return padrao


def main() -> int:
    carregar_arquivo_env()

    email = os.getenv("CONTHABIL_EMAIL", "").strip()
    senha = os.getenv("CONTHABIL_SENHA", "")
    if not email or not senha:
        registrar(
            "ERRO: configure CONTHABIL_EMAIL e CONTHABIL_SENHA no arquivo "
            f"{BASE / '.env'} antes de executar."
        )
        return 2

    simular = os.getenv("CONTHABIL_SIMULAR", "nao").strip().lower() in {
        "1",
        "sim",
        "true",
        "yes",
    }
    pasta_dados = pasta_de_dados()
    pasta_dados.mkdir(parents=True, exist_ok=True)

    try:
        registrar("Autenticando no portal Conthabil...")
        cliente = ClienteConthabil()
        cliente.login(email, senha)
        registrar("Login no Conthabil concluido.")

        pasta_credenciais = pasta_credenciais_drive()
        registrar(f"Usando credenciais do Google Drive em {pasta_credenciais}")

        drive = DriveCertificados(
            pasta_credenciais,
            os.getenv("GOOGLE_DRIVE_PASTA_E_CNPJ_ID", PASTAS_PADRAO["drive"]).strip()
            or PASTAS_PADRAO["drive"],
        )

        renovador = Renovador(cliente, drive, pasta_dados, registrar)
        resultado = renovador.executar(
            simular=simular,
            tamanho_lote=ler_inteiro("CONTHABIL_LOTE", 10),
            confirmar_final=not simular,
        )
    except (ErroConthabil, ErroDrive) as erro:
        registrar(f"ERRO: {erro}")
        return 2
    except KeyboardInterrupt:
        registrar("Cancelado pelo usuario.")
        return 130
    except Exception as erro:  # noqa: BLE001 - erro exibido no painel
        registrar(f"ERRO inesperado: {erro}")
        return 3

    registrar("")
    registrar("=" * 60)
    registrar(f"Vencidos analisados ....: {resultado.total_vencidos}")
    registrar(f"Importados com sucesso .: {resultado.importados}")
    for status, texto in STATUS.items():
        quantidade = resultado.contar(status)
        if quantidade and status != "IMPORTADO":
            registrar(f"{texto:<24}: {quantidade}")
    if resultado.pasta_relatorio:
        registrar(f"Relatorio ..............: {resultado.pasta_relatorio}")
    registrar("=" * 60)

    if simular:
        return 0
    return 0 if resultado.importados or resultado.total_vencidos == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
