"""Cliente somente de leitura para a API da aplicação WhatsContábil."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


class ErroWhatsContabil(Exception):
    """Erro compreensível ao acessar a API da WhatsContábil."""


def carregar_configuracao(pasta_projeto):
    """Carrega URL e token do .env sem expor o token no terminal."""
    pasta_projeto = Path(pasta_projeto)
    load_dotenv(pasta_projeto / ".env")

    url_base = os.getenv("WHATSCONTABIL_URL", "").strip().rstrip("/")
    token = os.getenv("WHATSCONTABIL_TOKEN", "").strip()

    if not url_base:
        raise ErroWhatsContabil(
            "WHATSCONTABIL_URL não foi configurada no arquivo .env."
        )
    if not token:
        raise ErroWhatsContabil(
            "WHATSCONTABIL_TOKEN não foi configurado no arquivo .env."
        )

    endereco = urlparse(url_base)
    if endereco.scheme not in {"http", "https"} or not endereco.netloc:
        raise ErroWhatsContabil(
            "WHATSCONTABIL_URL é inválida. Informe a URL completa, "
            "começando com https://."
        )

    return url_base, token


def _interpretar_erro_http(resposta):
    """Converte respostas HTTP comuns em mensagens seguras e claras."""
    mensagens = {
        400: "A API recusou os parâmetros da requisição.",
        401: "Token ausente, inválido ou expirado.",
        403: "Acesso negado pela API. Verifique o token e as permissões.",
        404: "Endpoint não encontrado. Verifique a URL configurada.",
        429: "Limite de requisições atingido. Tente novamente mais tarde.",
    }
    mensagem = mensagens.get(
        resposta.status_code,
        f"A API respondeu com o status HTTP {resposta.status_code}.",
    )

    # A WhatsContabil costuma devolver o motivo real em JSON. Mantemos apenas
    # campos textuais conhecidos, limitados em tamanho, para ajudar no
    # diagnostico sem registrar token, cabecalhos ou o corpo completo.
    detalhe = ""
    try:
        conteudo = resposta.json()
    except ValueError:
        conteudo = None

    if isinstance(conteudo, dict):
        candidatos = (
            conteudo.get("message"),
            conteudo.get("error"),
            conteudo.get("detail"),
            conteudo.get("details"),
        )
        detalhe = next(
            (
                str(valor).strip()
                for valor in candidatos
                if isinstance(valor, (str, int, float))
                and str(valor).strip()
            ),
            "",
        )

    if detalhe:
        detalhe = re.sub(r"\s+", " ", detalhe)[:500]
        mensagem = f"{mensagem} Detalhe da API: {detalhe}"
    raise ErroWhatsContabil(mensagem)


def listar_conexoes(pasta_projeto, timeout=30):
    """Executa somente GET /api/whatsapps e retorna as conexões cadastradas."""
    url_base, token = carregar_configuracao(pasta_projeto)
    url = f"{url_base}/api/whatsapps"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as erro:
        raise ErroWhatsContabil(
            "A API demorou mais de 30 segundos para responder."
        ) from erro
    except requests.ConnectionError as erro:
        raise ErroWhatsContabil(
            "Não foi possível conectar à API. Verifique a URL e a rede."
        ) from erro
    except requests.RequestException as erro:
        raise ErroWhatsContabil(f"Falha na requisição: {erro}") from erro

    if not 200 <= resposta.status_code < 300:
        _interpretar_erro_http(resposta)

    try:
        conteudo = resposta.json()
    except ValueError as erro:
        raise ErroWhatsContabil(
            "A API respondeu com sucesso, mas o conteúdo não é JSON válido."
        ) from erro

    if isinstance(conteudo, list):
        return conteudo
    if isinstance(conteudo, dict):
        # A documentação mostra tanto objeto único quanto lista.
        for chave in ("whatsapps", "connections", "data"):
            if isinstance(conteudo.get(chave), list):
                return conteudo[chave]
        return [conteudo]

    raise ErroWhatsContabil("A API retornou um formato de dados inesperado.")


def obter_conexao_oficial(conexoes):
    """Seleciona a única conexão oficial que esteja conectada."""
    oficiais_conectadas = [
        conexao
        for conexao in conexoes
        if conexao.get("isOfficial") in (1, True, "1")
        and str(conexao.get("status", "")).strip().upper() == "CONNECTED"
    ]

    if not oficiais_conectadas:
        raise ErroWhatsContabil(
            "Nenhuma conexão oficial com status CONNECTED foi encontrada."
        )
    if len(oficiais_conectadas) > 1:
        raise ErroWhatsContabil(
            "Mais de uma conexão oficial está conectada. Será necessário "
            "informar explicitamente qual whatsappId utilizar."
        )

    return oficiais_conectadas[0]


def listar_templates(pasta_projeto, whatsapp_id, timeout=30):
    """Consulta os templates da conexão sem enviar mensagens."""
    url_base, token = carregar_configuracao(pasta_projeto)
    url = f"{url_base}/api/templates/{whatsapp_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as erro:
        raise ErroWhatsContabil(
            "A consulta de templates demorou mais de 30 segundos."
        ) from erro
    except requests.ConnectionError as erro:
        raise ErroWhatsContabil(
            "Não foi possível conectar à API para consultar templates."
        ) from erro
    except requests.RequestException as erro:
        raise ErroWhatsContabil(f"Falha na requisição: {erro}") from erro

    if not 200 <= resposta.status_code < 300:
        _interpretar_erro_http(resposta)

    try:
        conteudo = resposta.json()
    except ValueError as erro:
        raise ErroWhatsContabil(
            "A resposta dos templates não é um JSON válido."
        ) from erro

    if isinstance(conteudo, list):
        return conteudo
    if isinstance(conteudo, dict):
        for chave in ("templates", "data"):
            if isinstance(conteudo.get(chave), list):
                return conteudo[chave]
        return [conteudo]

    raise ErroWhatsContabil("A API retornou templates em formato inesperado.")


def normalizar_telefone_brasil(telefone, ddd_padrao=None):
    """Converte um telefone brasileiro para DDI + DDD + número."""
    digitos = re.sub(r"\D", "", str(telefone or ""))
    ddd = re.sub(r"\D", "", str(ddd_padrao or ""))

    if len(digitos) in (8, 9) and len(ddd) == 2:
        digitos = f"{ddd}{digitos}"

    if len(digitos) in (10, 11):
        digitos = f"55{digitos}"

    if len(digitos) not in (12, 13) or not digitos.startswith("55"):
        raise ErroWhatsContabil(
            "Telefone inválido. Informe DDD e número; o DDI 55 é opcional."
        )

    return digitos


def enviar_template(
    pasta_projeto,
    telefone,
    nome_template,
    whatsapp_id,
    variaveis=None,
    arquivo=None,
    timeout=30,
):
    """Envia um template oficial. Não repete automaticamente em caso de erro."""
    url_base, token = carregar_configuracao(pasta_projeto)
    destinatario = normalizar_telefone_brasil(telefone)
    url = f"{url_base}/api/messages/send"
    headers = {"Authorization": f"Bearer {token}"}

    dados = {
        "to": destinatario,
        "template": str(nome_template),
        "whatsappId": str(whatsapp_id),
    }
    if variaveis is not None:
        dados["message"] = json.dumps(
            list(variaveis),
            ensure_ascii=False,
        )

    arquivo_aberto = None
    arquivos = None
    if arquivo is not None:
        caminho_arquivo = Path(arquivo)
        if not caminho_arquivo.is_file():
            raise ErroWhatsContabil(
                "O arquivo do relatorio nao foi encontrado para o envio."
            )
        if caminho_arquivo.stat().st_size > 20 * 1024 * 1024:
            raise ErroWhatsContabil(
                "O arquivo do relatorio ultrapassa o limite de 20 MB da API."
            )
        arquivo_aberto = caminho_arquivo.open("rb")
        # A API da WhatsContabil espera exatamente o objeto do arquivo neste
        # campo. O requests monta filename e Content-Length no multipart.
        arquivos = {"files": arquivo_aberto}

    try:
        if arquivos is not None:
            resposta = requests.post(
                url,
                headers=headers,
                data=dados,
                files=arquivos,
                timeout=timeout,
            )
        else:
            # MantǸm o fluxo jǭ validado dos templates sem anexo.
            campos_multipart = {
                chave: (None, valor) for chave, valor in dados.items()
            }
            resposta = requests.post(
                url,
                headers=headers,
                files=campos_multipart,
                timeout=timeout,
            )
    except requests.Timeout as erro:
        raise ErroWhatsContabil(
            "O envio demorou mais de 30 segundos. O resultado ficou incerto; "
            "não repita antes de consultar o histórico."
        ) from erro
    except requests.ConnectionError as erro:
        raise ErroWhatsContabil(
            "Não foi possível conectar à API durante o envio."
        ) from erro
    except requests.RequestException as erro:
        raise ErroWhatsContabil(f"Falha na requisição: {erro}") from erro
    finally:
        if arquivo_aberto is not None:
            arquivo_aberto.close()

    if not 200 <= resposta.status_code < 300:
        _interpretar_erro_http(resposta)

    try:
        conteudo = resposta.json()
    except ValueError:
        conteudo = {"message": resposta.text.strip() or "Envio aceito pela API."}

    return {
        "destinatario": destinatario,
        "status_http": resposta.status_code,
        "resposta": conteudo,
    }


def enviar_midia(
    pasta_projeto,
    telefone,
    mensagem,
    whatsapp_id,
    arquivo,
    timeout=30,
):
    """Envia um arquivo como midia em uma conversa que ja foi aberta."""
    url_base, token = carregar_configuracao(pasta_projeto)
    destinatario = normalizar_telefone_brasil(telefone)
    mensagem = str(mensagem or "").strip()
    caminho_arquivo = Path(arquivo)

    if not mensagem:
        raise ErroWhatsContabil("A legenda da midia nao pode estar vazia.")
    if len(mensagem) > 2000:
        raise ErroWhatsContabil(
            "A legenda da midia ultrapassa o limite de 2.000 caracteres."
        )
    if not caminho_arquivo.is_file():
        raise ErroWhatsContabil("O arquivo da midia nao foi encontrado.")
    if caminho_arquivo.stat().st_size > 20 * 1024 * 1024:
        raise ErroWhatsContabil(
            "O arquivo da midia ultrapassa o limite de 20 MB da API."
        )

    url = f"{url_base}/api/messages/send"
    headers = {"Authorization": f"Bearer {token}"}
    arquivo_aberto = caminho_arquivo.open("rb")
    campos = {
        "to": (None, destinatario),
        "message": (None, mensagem),
        "whatsappId": (None, str(whatsapp_id)),
        "medias": arquivo_aberto,
    }

    try:
        resposta = requests.post(
            url,
            headers=headers,
            files=campos,
            timeout=timeout,
        )
    except requests.Timeout as erro:
        raise ErroWhatsContabil(
            "O envio da midia demorou mais de 30 segundos. O resultado ficou "
            "incerto; nao repita antes de consultar o historico."
        ) from erro
    except requests.ConnectionError as erro:
        raise ErroWhatsContabil(
            "Nao foi possivel conectar a API durante o envio da midia."
        ) from erro
    except requests.RequestException as erro:
        raise ErroWhatsContabil(f"Falha na requisicao da midia: {erro}") from erro
    finally:
        arquivo_aberto.close()

    if not 200 <= resposta.status_code < 300:
        _interpretar_erro_http(resposta)

    try:
        conteudo = resposta.json()
    except ValueError:
        conteudo = {"message": resposta.text.strip() or "Midia aceita pela API."}

    return {
        "destinatario": destinatario,
        "status_http": resposta.status_code,
        "resposta": conteudo,
    }


def enviar_mensagem_texto(
    pasta_projeto,
    telefone,
    mensagem,
    whatsapp_id,
    timeout=30,
):
    """Envia texto em uma conversa já aberta na WhatsContábil."""
    url_base, token = carregar_configuracao(pasta_projeto)
    destinatario = normalizar_telefone_brasil(telefone)
    mensagem = str(mensagem or "").strip()

    if not mensagem:
        raise ErroWhatsContabil("A mensagem de texto não pode estar vazia.")
    if len(mensagem) > 2000:
        raise ErroWhatsContabil(
            "A mensagem ultrapassa o limite de 2.000 caracteres da API."
        )

    url = f"{url_base}/api/messages/send"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    }
    dados = {
        "to": destinatario,
        "message": mensagem,
        "whatsappId": str(whatsapp_id),
    }

    try:
        # Envia bytes UTF-8 explicitamente. Isso evita que acentos e cedilhas
        # sejam substituídos por "?" em ambientes Windows.
        corpo_utf8 = json.dumps(
            dados,
            ensure_ascii=False,
        ).encode("utf-8")
        resposta = requests.post(
            url,
            headers=headers,
            data=corpo_utf8,
            timeout=timeout,
        )
    except requests.Timeout as erro:
        raise ErroWhatsContabil(
            "O envio demorou mais de 30 segundos. O resultado ficou incerto; "
            "não repita antes de consultar o histórico."
        ) from erro
    except requests.ConnectionError as erro:
        raise ErroWhatsContabil(
            "Não foi possível conectar à API durante o envio."
        ) from erro
    except requests.RequestException as erro:
        raise ErroWhatsContabil(f"Falha na requisição: {erro}") from erro

    if not 200 <= resposta.status_code < 300:
        _interpretar_erro_http(resposta)

    try:
        conteudo = resposta.json()
    except ValueError:
        conteudo = {"message": resposta.text.strip() or "Envio aceito pela API."}

    return {
        "destinatario": destinatario,
        "status_http": resposta.status_code,
        "resposta": conteudo,
    }
