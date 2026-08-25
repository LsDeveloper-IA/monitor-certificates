import base64
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from utils.caminhos import obter_pasta_aplicacao


ESCOPO_EMAIL_SMTP = ["https://mail.google.com/"]


class ErroEmailGoogle(RuntimeError):
    """Erro compreensível durante autenticação ou envio pelo Gmail."""


def obter_credenciais(pasta_projeto=None):
    """Obtém credenciais OAuth exclusivas para o envio de e-mail."""
    if pasta_projeto is None:
        pasta_projeto = obter_pasta_aplicacao()
    else:
        pasta_projeto = Path(pasta_projeto)

    arquivo_credentials = pasta_projeto / "credentials.json"
    arquivo_token_email = pasta_projeto / "token_email.json"
    credenciais = None

    if not arquivo_credentials.exists():
        raise ErroEmailGoogle("O arquivo credentials.json não foi encontrado.")

    if arquivo_token_email.exists():
        credenciais = Credentials.from_authorized_user_file(
            arquivo_token_email,
            ESCOPO_EMAIL_SMTP,
        )

    try:
        if not credenciais or not credenciais.valid:
            if (
                credenciais
                and credenciais.expired
                and credenciais.refresh_token
            ):
                credenciais.refresh(Request())
            else:
                fluxo = InstalledAppFlow.from_client_secrets_file(
                    arquivo_credentials,
                    ESCOPO_EMAIL_SMTP,
                )
                credenciais = fluxo.run_local_server(port=0)

            arquivo_token_email.write_text(
                credenciais.to_json(),
                encoding="utf-8",
            )
    except Exception as erro:
        raise ErroEmailGoogle(
            f"Não foi possível concluir a autorização OAuth: {erro}"
        ) from erro

    return credenciais


def enviar_email(destinatario, assunto, mensagem, mensagem_html=None):
    """Envia um e-mail pelo SMTP do Gmail usando OAuth2/XOAUTH2."""
    pasta_projeto = obter_pasta_aplicacao()
    load_dotenv(pasta_projeto / ".env")

    remetente = os.getenv("EMAIL_REMETENTE", "").strip()
    if not remetente:
        raise ErroEmailGoogle(
            "Preencha EMAIL_REMETENTE no arquivo .env antes do teste."
        )

    if not destinatario or "@" not in destinatario:
        raise ErroEmailGoogle("O destinatário informado não é válido.")

    credenciais = obter_credenciais(pasta_projeto)
    if not credenciais.token:
        raise ErroEmailGoogle("O Google não retornou um access token válido.")

    email = EmailMessage()
    email["From"] = remetente
    email["To"] = destinatario
    email["Subject"] = assunto
    email["Date"] = formatdate(localtime=True)
    email["Message-ID"] = make_msgid()
    email.set_content(mensagem)

    if mensagem_html:
        email.add_alternative(mensagem_html, subtype="html")

    autenticacao = (
        f"user={remetente}\x01auth=Bearer {credenciais.token}\x01\x01"
    )
    autenticacao_base64 = base64.b64encode(
        autenticacao.encode("utf-8")
    ).decode("ascii")

    try:
        contexto_ssl = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            context=contexto_ssl,
            timeout=30,
        ) as servidor:
            # O Gmail exige a identificação EHLO antes do AUTH XOAUTH2.
            codigo_ehlo, resposta_ehlo = servidor.ehlo()
            if codigo_ehlo != 250:
                raise ErroEmailGoogle(
                    "O Gmail recusou a identificação EHLO: "
                    f"{codigo_ehlo} {resposta_ehlo!r}"
                )

            codigo, resposta = servidor.docmd(
                "AUTH",
                "XOAUTH2 " + autenticacao_base64,
            )

            if codigo != 235:
                raise ErroEmailGoogle(
                    "O Gmail recusou a autenticação XOAUTH2: "
                    f"{codigo} {resposta!r}"
                )

            recusados = servidor.send_message(email)
            if recusados:
                raise ErroEmailGoogle(
                    "O servidor recusou um ou mais destinatários: "
                    f"{', '.join(recusados)}"
                )
    except (OSError, smtplib.SMTPException) as erro:
        raise ErroEmailGoogle(
            f"Não foi possível enviar o e-mail pelo Gmail: {erro}"
        ) from erro

    return email["Message-ID"]
