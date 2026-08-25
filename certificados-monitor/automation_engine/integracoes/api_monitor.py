import os
from datetime import date, datetime

import requests
from dotenv import load_dotenv


class ErroIntegracaoApi(RuntimeError):
    pass


def _serializar_data(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()[:10]
    return str(valor)[:10] if valor else None


def _primeiro_telefone(item):
    cliente = item.get("dados_cliente") or {}
    if cliente.get("telefone"):
        return cliente["telefone"]
    for contato in cliente.get("contatos") or []:
        if contato.get("telefone"):
            return contato["telefone"]
    return None


def _primeiro_responsavel(item):
    cliente = item.get("dados_cliente") or {}
    for socio in cliente.get("socios") or []:
        if socio.get("nome"):
            return socio["nome"]
    for contato in cliente.get("contatos") or []:
        if contato.get("nome"):
            return contato["nome"]
    return None


def sincronizar_com_api(pasta_projeto, resultados):
    """Envia em lote somente os campos necessarios para o sistema web."""
    load_dotenv(pasta_projeto / ".env")
    url_base = os.getenv("API_MONITOR_URL", "").strip().rstrip("/")
    chave = os.getenv("INTEGRACAO_API_KEY", "").strip()
    if not url_base:
        raise ErroIntegracaoApi("API_MONITOR_URL não foi configurada no .env")
    if not chave:
        raise ErroIntegracaoApi("INTEGRACAO_API_KEY não foi configurada no .env")

    certificados = []
    for item in resultados:
        if not item.get("cnpj") or not item.get("vencimento"):
            continue
        certificados.append(
            {
                "empresa": item.get("empresa"),
                "arquivo": item.get("arquivo"),
                "cnpj": item.get("cnpj"),
                "vencimento": _serializar_data(item.get("vencimento")),
                "email": item.get("email"),
                "telefone": _primeiro_telefone(item),
                "responsavel": _primeiro_responsavel(item),
                "observacao": item.get("observacao"),
            }
        )

    try:
        resposta = requests.post(
            f"{url_base}/api/certificados/sincronizar",
            headers={"X-API-Key": chave},
            json={
                "certificados": certificados,
                "substituir_lista": True,
            },
            timeout=60,
        )
    except requests.RequestException as erro:
        raise ErroIntegracaoApi(f"Não foi possível acessar a API: {erro}") from erro

    try:
        conteudo = resposta.json()
    except ValueError:
        conteudo = {}
    if resposta.status_code not in {200, 207}:
        detalhe = conteudo.get("erro") or f"HTTP {resposta.status_code}"
        raise ErroIntegracaoApi(f"A API recusou a sincronização: {detalhe}")
    return conteudo
