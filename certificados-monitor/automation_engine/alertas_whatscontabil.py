"""Alertas internos de certificados enviados pela aplicação WhatsContábil."""

import re
from time import sleep

from integracoes.whatscontabil import (
    ErroWhatsContabil,
    enviar_mensagem_texto,
    normalizar_telefone_brasil,
)
from registro_alertas import (
    alerta_ja_enviado,
    alerta_ja_possui_algum_envio,
    registrar_alerta_enviado,
)


DIAS_MINIMOS_ALERTA = 1
DIAS_MAXIMOS_ALERTA = 30
LIMITE_MENSAGEM = 2000


def preparar_alertas_internos(resultados):
    """Seleciona certificados entre 1 e 30 dias para aviso ou recuperação."""
    return [
        {
            "cnpj": resultado.get("cnpj"),
            "empresa": resultado.get("empresa"),
            "arquivo": resultado.get("arquivo"),
            "vencimento": resultado.get("vencimento"),
            "dias": resultado.get("dias"),
            "email": resultado.get("email"),
            "dados_cliente": resultado.get("dados_cliente"),
            "tipo_aviso": (
                f"aviso_{resultado.get('dias')}"
                if resultado.get("dias") in {30, 15}
                else "recuperacao"
            ),
        }
        for resultado in resultados
        if isinstance(resultado.get("dias"), int)
        and DIAS_MINIMOS_ALERTA <= resultado["dias"] <= DIAS_MAXIMOS_ALERTA
    ]


def _separar_emails_validos(valor):
    padrao = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    emails = []
    for parte in re.split(r"[;,]", str(valor or "")):
        email = parte.strip().casefold()
        if email and padrao.fullmatch(email) and email not in emails:
            emails.append(email)
    return emails


def _obter_telefones_validos(alerta):
    dados_cliente = alerta.get("dados_cliente") or {}
    ddd_padrao = dados_cliente.get("ddd")
    candidatos = [dados_cliente.get("telefone")]
    candidatos.extend(
        contato.get("telefone")
        for contato in dados_cliente.get("contatos", [])
    )
    telefones = []
    for candidato in candidatos:
        try:
            telefone = normalizar_telefone_brasil(candidato, ddd_padrao)
        except ErroWhatsContabil:
            continue
        if telefone not in telefones:
            telefones.append(telefone)
    return telefones


def classificar_alertas_por_contato(alertas):
    """Separa empresas com telefone das que exigem pesquisa pela equipe."""
    com_contato = []
    para_equipe = []

    for alerta_original in alertas:
        alerta = dict(alerta_original)
        alerta["emails_validos"] = _separar_emails_validos(alerta.get("email"))
        alerta["telefones_validos"] = _obter_telefones_validos(alerta)
        alerta["dados_faltantes"] = []
        if not alerta["telefones_validos"]:
            alerta["dados_faltantes"].append("telefone")
        if not alerta["emails_validos"]:
            alerta["dados_faltantes"].append("e-mail")

        # O WhatsApp depende somente de telefone. O e-mail continua no
        # relatório como informação complementar, mas não bloqueia o envio.
        if alerta["telefones_validos"]:
            com_contato.append(alerta)

        # Os grupos podem se sobrepor: com telefone a empresa pode receber o
        # WhatsApp, mas qualquer dado ausente ainda deve ser corrigido.
        if alerta["dados_faltantes"]:
            para_equipe.append(alerta)

    return com_contato, para_equipe


def _formatar_cnpj(cnpj):
    numeros = "".join(caractere for caractere in str(cnpj or "") if caractere.isdigit())
    if len(numeros) != 14:
        return str(cnpj or "não informado")
    return (
        f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/"
        f"{numeros[8:12]}-{numeros[12:]}"
    )


def _montar_bloco(alerta):
    vencimento = alerta.get("vencimento")
    if hasattr(vencimento, "strftime"):
        vencimento = vencimento.strftime("%d/%m/%Y")
    else:
        vencimento = str(vencimento or "não informado")

    return (
        f"Empresa: {alerta.get('empresa') or 'não informada'}\n"
        f"CNPJ: {_formatar_cnpj(alerta.get('cnpj'))}\n"
        f"Vencimento: {vencimento}\n"
        f"Prazo: {alerta.get('dias')} dias\n"
        "Ação: entrar em contato para iniciar a renovação."
    )


def _montar_mensagem_cliente(alerta):
    vencimento = alerta.get("vencimento")
    if hasattr(vencimento, "strftime"):
        vencimento = vencimento.strftime("%d/%m/%Y")
    else:
        vencimento = str(vencimento or "não informado")
    return (
        "*AVISO DE VENCIMENTO - CERTIFICADO DIGITAL*\n\n"
        "Olá,\n\n"
        f"O certificado digital e-CNPJ da empresa "
        f"{alerta.get('empresa') or 'não informada'}, CNPJ "
        f"{_formatar_cnpj(alerta.get('cnpj'))}, vencerá em {vencimento}.\n\n"
        f"Faltam {alerta.get('dias')} dias para o vencimento. "
        "Entre em contato com a Office Contábil para iniciar o processo "
        "de renovação.\n\n"
        "Atenciosamente,\nOffice Contábil"
    )


def _montar_bloco_responsavel(alerta):
    bloco = _montar_bloco(alerta)
    telefones = ", ".join(alerta.get("telefones_validos", []))
    emails = ", ".join(alerta.get("emails_validos", [])) or "não localizado"
    return f"{bloco}\nTelefone(s): {telefones}\nE-mail(s): {emails}"


def _montar_bloco_equipe(alerta):
    bloco = _montar_bloco(alerta)
    faltantes = " e ".join(alerta.get("dados_faltantes", []))
    return f"{bloco}\nPendência: localizar/atualizar {faltantes}."


def _montar_relatorios(alertas, titulo, montar_bloco):
    cabecalho = f"*{titulo}*\n\n"
    rodape = "\n\nMensagem automática do Monitor de Certificados."
    pacotes = []
    texto_atual = cabecalho
    alertas_atuais = []
    for alerta in alertas:
        bloco = montar_bloco(alerta)
        separador = "\n\n--------------------\n\n" if alertas_atuais else ""
        if len(texto_atual + separador + bloco + rodape) > LIMITE_MENSAGEM and alertas_atuais:
            pacotes.append((texto_atual + rodape, alertas_atuais))
            texto_atual = cabecalho + bloco
            alertas_atuais = [alerta]
        else:
            texto_atual += separador + bloco
            alertas_atuais.append(alerta)
    if alertas_atuais:
        pacotes.append((texto_atual + rodape, alertas_atuais))
    return pacotes


def montar_mensagens_internas(alertas):
    """Consolida alertas respeitando o limite de 2.000 caracteres."""
    cabecalho = "*AVISO INTERNO - CERTIFICADOS DIGITAIS*\n\n"
    rodape = "\n\nMensagem automática do Monitor de Certificados."
    pacotes = []
    texto_atual = cabecalho
    alertas_atuais = []

    for alerta in alertas:
        bloco = _montar_bloco(alerta)
        separador = "\n\n--------------------\n\n" if alertas_atuais else ""
        candidato = texto_atual + separador + bloco + rodape

        if len(candidato) > LIMITE_MENSAGEM and alertas_atuais:
            pacotes.append((texto_atual + rodape, alertas_atuais))
            texto_atual = cabecalho + bloco
            alertas_atuais = [alerta]
        else:
            texto_atual += separador + bloco
            alertas_atuais.append(alerta)

    if alertas_atuais:
        pacotes.append((texto_atual + rodape, alertas_atuais))

    return pacotes


def simular_alertas_internos(alertas, telefone):
    """Mostra os três fluxos sem chamar a API."""
    print("---------------------------")
    print("SIMULAÇÃO WHATSCONTÁBIL - NENHUMA MENSAGEM SERÁ ENVIADA")
    print(f"Número de teste: {telefone or 'não configurado'}")

    if not alertas:
        print("Nenhum certificado está entre 1 e 30 dias do vencimento.")
        return

    com_contato, para_equipe = classificar_alertas_por_contato(alertas)
    relatorios_responsavel = _montar_relatorios(
        com_contato,
        "RELATORIO PARA O FUNCIONARIO RESPONSAVEL",
        _montar_bloco_responsavel,
    )
    relatorios_equipe = _montar_relatorios(
        para_equipe,
        "PENDENCIAS DE CONTATO PARA A EQUIPE",
        _montar_bloco_equipe,
    )
    print(f"Mensagens individuais de cliente: {len(com_contato)}")
    print(f"Relatorios para o responsavel: {len(relatorios_responsavel)}")
    print(f"Relatorios para a equipe: {len(relatorios_equipe)}")
    return
    print(f"Empresas com telefone válido: {len(com_contato)}")
    print(f"Empresas sem telefone encaminhadas para a equipe: {len(para_equipe)}")

    for alerta in com_contato:
        print("---------------------------")
        print("TESTE - MENSAGEM DESTINADA AO CLIENTE")
        print(_montar_mensagem_cliente(alerta))

    for mensagem, _ in _montar_relatorios(
        com_contato,
        "TESTE - RELATÓRIO PARA O FUNCIONÁRIO RESPONSÁVEL",
        _montar_bloco_responsavel,
    ):
        print(f"---------------------------\n{mensagem}")

    for mensagem, _ in _montar_relatorios(
        para_equipe,
        "TESTE - PENDÊNCIAS DE CONTATO PARA A EQUIPE",
        _montar_bloco_equipe,
    ):
        print(f"---------------------------\n{mensagem}")


def enviar_alertas_internos(alertas, pasta_projeto, telefone, whatsapp_id):
    """Executa os três fluxos usando somente o número de teste."""
    destinatario = normalizar_telefone_brasil(telefone)
    com_contato, para_equipe = classificar_alertas_por_contato(alertas)
    resumo = {
        "enviados": 0,
        "duplicados": 0,
        "falhas": 0,
        "detalhes_falhas": [],
        "message_ids": [],
    }

    def separar_pendentes(itens, tipo):
        resultado = []
        for alerta in itens:
            registro = dict(alerta)
            registro["email"] = f"whatsapp:{tipo}:{destinatario}"
            eh_recuperacao = alerta.get("tipo_aviso") == "recuperacao"

            if eh_recuperacao and alerta_ja_possui_algum_envio(registro):
                resumo["duplicados"] += 1
                continue
            if not eh_recuperacao and alerta_ja_enviado(registro):
                resumo["duplicados"] += 1
                continue

            # O valor zero identifica a recuperação independentemente do
            # dia em que ela aconteceu. Os avisos normais mantêm 30 ou 15.
            if eh_recuperacao:
                registro["dias"] = 0
            resultado.append((alerta, registro))
        return resultado

    cliente_pendentes = separar_pendentes(com_contato, "cliente_teste")
    responsavel_pendentes = separar_pendentes(com_contato, "responsavel_teste")
    equipe_pendentes = separar_pendentes(para_equipe, "equipe_teste")
    transmissoes = []

    for alerta, registro in cliente_pendentes:
        transmissoes.append(
            (
                "cliente",
                _montar_mensagem_cliente(alerta),
                [(alerta, registro)],
            )
        )

    mapa_responsavel = {id(alerta): registro for alerta, registro in responsavel_pendentes}
    for mensagem, itens in _montar_relatorios(
        [alerta for alerta, _ in responsavel_pendentes],
        "RELATÓRIO PARA O FUNCIONÁRIO RESPONSÁVEL",
        _montar_bloco_responsavel,
    ):
        transmissoes.append(
            (
                "responsável",
                mensagem,
                [(alerta, mapa_responsavel[id(alerta)]) for alerta in itens],
            )
        )

    mapa_equipe = {id(alerta): registro for alerta, registro in equipe_pendentes}
    for mensagem, itens in _montar_relatorios(
        [alerta for alerta, _ in equipe_pendentes],
        "PENDÊNCIAS DE CONTATO PARA A EQUIPE",
        _montar_bloco_equipe,
    ):
        transmissoes.append(
            (
                "equipe",
                mensagem,
                [(alerta, mapa_equipe[id(alerta)]) for alerta in itens],
            )
        )

    print(f"Mensagens de teste preparadas: {len(transmissoes)}")
    for numero, (tipo, mensagem, itens_registro) in enumerate(transmissoes, start=1):
        if numero > 1:
            sleep(5.1)
        try:
            resultado = enviar_mensagem_texto(
                pasta_projeto,
                destinatario,
                mensagem,
                whatsapp_id,
            )
            resposta = resultado.get("resposta") or {}
            ids = resposta.get("messageIds") or []
            resumo["message_ids"].extend(ids)

            for _, registro in itens_registro:
                registrar_alerta_enviado(registro)
                resumo["enviados"] += 1
            print(
                f"Mensagem de {tipo} {numero}/{len(transmissoes)} aceita "
                f"pela WhatsContábil ({len(itens_registro)} certificado(s))."
            )
        except (ErroWhatsContabil, OSError) as erro:
            resumo["falhas"] += len(itens_registro)
            for alerta, _ in itens_registro:
                resumo["detalhes_falhas"].append(
                    {
                        "empresa": alerta.get("empresa"),
                        "email": f"whatsapp:{destinatario}",
                        "erro": str(erro),
                    }
                )
            print(f"Falha no envio de {tipo}: {erro}")

    return resumo
