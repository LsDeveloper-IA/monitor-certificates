import re


DIAS_DE_ALERTA = {30, 15}
PADRAO_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def separar_emails(valor):
    """Separa e valida e-mails cadastrados com vírgula ou ponto e vírgula."""
    partes = re.split(r"[;,]", str(valor or ""))
    emails = []

    for parte in partes:
        email = parte.strip().casefold()
        if email and PADRAO_EMAIL.fullmatch(email) and email not in emails:
            emails.append(email)

    return emails


def preparar_alertas(resultados):
    """Monta alertas de 30 e 15 dias, mas não envia mensagens."""
    alertas = []

    for resultado in resultados:
        if resultado.get("dias") not in DIAS_DE_ALERTA:
            continue

        emails = separar_emails(resultado.get("email"))
        if not emails:
            continue

        for email in emails:
            alertas.append(
                {
                    "cnpj": resultado.get("cnpj"),
                    "empresa": resultado.get("empresa"),
                    "email": email,
                    "origem_email": resultado.get("origem_email"),
                    "arquivo": resultado.get("arquivo"),
                    "vencimento": resultado.get("vencimento"),
                    "dias": resultado.get("dias"),
                }
            )

    return alertas


def montar_email_alerta(alerta):
    """Monta assunto, texto simples e HTML sem realizar o envio."""
    empresa = alerta.get("empresa") or "Empresa"
    cnpj = alerta.get("cnpj") or "não informado"
    dias = alerta.get("dias")
    vencimento = alerta.get("vencimento")

    if hasattr(vencimento, "strftime"):
        vencimento_formatado = vencimento.strftime("%d/%m/%Y")
    else:
        vencimento_formatado = str(vencimento or "não informado")

    assunto = f"Aviso de vencimento do certificado digital - {empresa}"
    mensagem = (
        "Olá,\n\n"
        f"O certificado digital e-CNPJ da empresa {empresa}, "
        f"CNPJ {cnpj}, vencerá em {vencimento_formatado}.\n\n"
        f"Faltam {dias} dias para o vencimento. Recomendamos iniciar o "
        "processo de renovação para evitar interrupções.\n\n"
        "Em caso de dúvidas, entre em contato com o escritório.\n\n"
        "Atenciosamente,\n"
        "Equipe de Certificados Digitais"
    )
    mensagem_html = f"""
    <html>
      <body>
        <p>Olá,</p>
        <p>
          O certificado digital e-CNPJ da empresa <strong>{empresa}</strong>,
          CNPJ <strong>{cnpj}</strong>, vencerá em
          <strong>{vencimento_formatado}</strong>.
        </p>
        <p>
          Faltam <strong>{dias} dias</strong> para o vencimento.
          Recomendamos iniciar o processo de renovação para evitar
          interrupções.
        </p>
        <p>Em caso de dúvidas, entre em contato com o escritório.</p>
        <p>Atenciosamente,<br>Equipe de Certificados Digitais</p>
      </body>
    </html>
    """.strip()

    return assunto, mensagem, mensagem_html


def simular_alertas(alertas):
    """Exibe uma prévia dos alertas sem chamar o serviço de e-mail."""
    print("---------------------------")
    print("SIMULAÇÃO DE ALERTAS - NENHUM E-MAIL SERÁ ENVIADO")

    if not alertas:
        print("Nenhum certificado está exatamente nas faixas de 30 ou 15 dias.")
        return

    print(f"Alertas que seriam enviados: {len(alertas)}")
    print("Os corpos das mensagens foram ocultados para manter o terminal limpo.")
    return

    for numero, alerta in enumerate(alertas, start=1):
        assunto, mensagem, _ = montar_email_alerta(alerta)
        print("---------------------------")
        print(f"Alerta {numero} de {len(alertas)}")
        print(f"Destinatário: {alerta['email']}")
        print(f"Origem do e-mail: {alerta.get('origem_email')}")
        print(f"Assunto: {assunto}")
        print("Mensagem:")
        print(mensagem)


def enviar_alertas(alertas):
    """Envia alertas ainda não registrados e retorna um resumo detalhado."""
    from integracoes.email_google import ErroEmailGoogle, enviar_email
    from registro_alertas import alerta_ja_enviado, registrar_alerta_enviado

    resumo = {
        "enviados": 0,
        "duplicados": 0,
        "falhas": 0,
        "detalhes_falhas": [],
        "message_ids": [],
    }

    for numero, alerta in enumerate(alertas, start=1):
        print("---------------------------")
        print(f"Processando alerta {numero} de {len(alertas)}")
        print(f"Empresa: {alerta.get('empresa')}")
        print(f"Destinatário: {alerta.get('email')}")

        if alerta_ja_enviado(alerta):
            resumo["duplicados"] += 1
            print("Ignorado: este alerta já foi enviado.")
            continue

        assunto, mensagem, mensagem_html = montar_email_alerta(alerta)

        try:
            message_id = enviar_email(
                destinatario=alerta["email"],
                assunto=assunto,
                mensagem=mensagem,
                mensagem_html=mensagem_html,
            )
            registrar_alerta_enviado(alerta)
            resumo["enviados"] += 1
            resumo["message_ids"].append(message_id)
            print(f"Aceito pelo Gmail. Message-ID: {message_id}")
        except (ErroEmailGoogle, OSError) as erro:
            resumo["falhas"] += 1
            resumo["detalhes_falhas"].append(
                {
                    "empresa": alerta.get("empresa"),
                    "email": alerta.get("email"),
                    "erro": str(erro),
                }
            )
            print(f"Falha no envio: {erro}")

    return resumo
