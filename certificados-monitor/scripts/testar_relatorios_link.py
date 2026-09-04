"""Gera e envia somente os dois relatorios internos ao numero de teste."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv


PASTA_BACKEND = Path(__file__).resolve().parents[1]
PASTA_MOTOR = PASTA_BACKEND / "automation_engine"
if str(PASTA_MOTOR) not in sys.path:
    sys.path.insert(0, str(PASTA_MOTOR))

from alertas_whatscontabil import (  # noqa: E402
    classificar_alertas_por_contato,
    criar_relatorio_pdf,
    preparar_alertas_internos,
)
from banco.conexao import conectar_banco  # noqa: E402
from banco.consultas import (  # noqa: E402
    buscar_clientes_por_cnpjs,
    normalizar_cnpj,
    preencher_dados_clientes,
)
from integracoes.google_drive import (  # noqa: E402
    enviar_relatorio_drive,
    obter_link_relatorio,
)
from integracoes.whatscontabil import (  # noqa: E402
    enviar_template,
    listar_templates,
    normalizar_telefone_brasil,
)


def carregar_resultados_site():
    """Lê o SQLite em modo somente leitura."""
    banco = (PASTA_BACKEND / "src" / "database" / "app.db").resolve()
    conexao = sqlite3.connect(f"file:{banco.as_posix()}?mode=ro", uri=True)
    try:
        linhas = conexao.execute(
            """
            SELECT nome_empresa, cpf_cnpj, data_vencimento, arquivo_drive_id
            FROM certificado
            WHERE ativo = 1
            """
        ).fetchall()
    finally:
        conexao.close()

    resultados = []
    from datetime import date

    hoje = date.today()
    for empresa, cnpj, vencimento, arquivo in linhas:
        try:
            cnpj = normalizar_cnpj(cnpj)
            data_vencimento = date.fromisoformat(str(vencimento)[:10])
        except (TypeError, ValueError):
            continue
        resultados.append({
            "empresa": empresa,
            "cnpj": cnpj,
            "arquivo": arquivo,
            "vencimento": data_vencimento,
            "dias": (data_vencimento - hoje).days,
            "email": None,
            "dados_cliente": None,
        })
    return resultados


def validar_configuracao():
    modo = os.getenv("MODO_WHATSCONTABIL", "").strip().casefold()
    if modo != "teste":
        raise RuntimeError("MODO_WHATSCONTABIL precisa estar como teste.")

    numero = normalizar_telefone_brasil(
        os.getenv("WHATSCONTABIL_NUMERO_TESTE", "")
    )
    whatsapp_id = os.getenv("WHATSCONTABIL_WHATSAPP_ID", "").strip()
    template = os.getenv(
        "WHATSCONTABIL_TEMPLATE_RELATORIO_LINK_TESTE",
        "",
    ).strip()
    if not whatsapp_id.isdigit():
        raise RuntimeError("WHATSCONTABIL_WHATSAPP_ID precisa ser numerico.")
    if not template:
        raise RuntimeError("O template de relatorio por link nao foi configurado.")

    templates = listar_templates(PASTA_MOTOR, whatsapp_id)
    encontrado = next(
        (item for item in templates if item.get("name") == template),
        None,
    )
    if not encontrado or str(encontrado.get("status", "")).upper() != "APPROVED":
        raise RuntimeError("O template de relatorio por link nao esta aprovado.")
    return numero, int(whatsapp_id), template


def enviar_relatorio(tipo, alertas, nome, numero, whatsapp_id, template):
    pasta_relatorios = PASTA_MOTOR / "relatorios" / "whatscontabil"
    caminho = criar_relatorio_pdf(alertas, tipo, pasta_relatorios)
    arquivo_drive = enviar_relatorio_drive(caminho, PASTA_MOTOR)
    link = obter_link_relatorio(arquivo_drive)
    descricao = (
        f"{len(alertas)} certificados proximos do vencimento"
        if tipo == "responsavel"
        else f"{len(alertas)} empresas com pendencias de contato"
    )
    return enviar_template(
        PASTA_MOTOR,
        numero,
        template,
        whatsapp_id,
        [nome, descricao, link],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmar-envio", action="store_true")
    argumentos = parser.parse_args()
    if not argumentos.confirmar_envio:
        raise SystemExit(
            "Envio bloqueado. Use --confirmar-envio para enviar ao numero de teste."
        )

    load_dotenv(PASTA_BACKEND / ".env")
    numero, whatsapp_id, template = validar_configuracao()
    resultados = carregar_resultados_site()

    conexao_banco = conectar_banco()
    try:
        clientes = buscar_clientes_por_cnpjs(
            conexao_banco,
            [item["cnpj"] for item in resultados],
        )
    finally:
        conexao_banco.close()
    preencher_dados_clientes(resultados, clientes)

    alertas = preparar_alertas_internos(resultados)
    responsavel, equipe = classificar_alertas_por_contato(alertas)
    print(f"Certificados no relatorio do responsavel: {len(responsavel)}")
    print(f"Empresas no relatorio da equipe: {len(equipe)}")

    envios = []
    falhas = []
    if responsavel:
        try:
            envios.append(enviar_relatorio(
                "responsavel",
                responsavel,
                os.getenv(
                    "WHATSCONTABIL_NOME_RESPONSAVEL_TESTE",
                    "Responsavel",
                ).strip() or "Responsavel",
                numero,
                whatsapp_id,
                template,
            ))
        except Exception as erro:
            falhas.append(("responsavel", str(erro)))
            print(f"Falha no relatorio do responsavel: {erro}")
    if equipe:
        try:
            envios.append(enviar_relatorio(
                "equipe",
                equipe,
                os.getenv(
                    "WHATSCONTABIL_NOME_DESTINATARIO_TESTE",
                    "Equipe Office",
                ).strip() or "Equipe Office",
                numero,
                whatsapp_id,
                template,
            ))
        except Exception as erro:
            falhas.append(("equipe", str(erro)))
            print(f"Falha no relatorio da equipe: {erro}")

    print(f"Relatorios aceitos pela WhatsContabil: {len(envios)}")
    print(f"Falhas nos relatorios: {len(falhas)}")
    print("Nenhum aviso individual de cliente foi enviado.")


if __name__ == "__main__":
    main()
