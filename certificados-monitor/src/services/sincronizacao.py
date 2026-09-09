import re
from datetime import datetime, timezone

from src.models.certificado import Certificado, db


def normalizar_documento(valor):
    documento = re.sub(r"\D", "", str(valor or ""))
    if len(documento) not in {11, 14}:
        raise ValueError("CPF/CNPJ deve possuir 11 ou 14 dígitos")
    return documento


def converter_data(valor):
    if not valor:
        raise ValueError("vencimento não informado")
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError as erro:
        raise ValueError("vencimento deve estar no formato YYYY-MM-DD") from erro


def sincronizar_certificados(itens, substituir_lista=False):
    """Cria ou atualiza certificados usando documento e arquivo."""
    if not isinstance(itens, list):
        raise ValueError("certificados deve ser uma lista")

    resumo = {
        "recebidos": len(itens),
        "criados": 0,
        "atualizados": 0,
        "desativados": 0,
        "inalterados": 0,
        "alteracoes_certificados": [],
        "rejeitados": [],
    }
    chaves_recebidas = set()
    certificados_anteriores = Certificado.query.filter_by(ativo=True).all()
    primeira_carga = not certificados_anteriores
    resumo["primeira_carga"] = primeira_carga
    ativos_por_documento = {}
    for item_anterior in certificados_anteriores:
        ativos_por_documento.setdefault(item_anterior.cpf_cnpj, []).append(
            item_anterior
        )

    try:
        for indice, item in enumerate(itens):
            try:
                if not isinstance(item, dict):
                    raise ValueError("item deve ser um objeto JSON")

                documento = normalizar_documento(
                    item.get("cnpj") or item.get("cpf_cnpj")
                )
                nome = str(
                    item.get("empresa") or item.get("nome_empresa") or ""
                ).strip()
                if not nome:
                    raise ValueError("empresa não informada")

                arquivo = str(
                    item.get("arquivo") or item.get("arquivo_drive_id") or ""
                ).strip()
                if not arquivo:
                    raise ValueError("arquivo do certificado nao informado")

                certificado = Certificado.query.filter_by(
                    cpf_cnpj=documento,
                    arquivo_drive_id=arquivo,
                ).first()
                novo = certificado is None
                if novo:
                    certificado = Certificado(cpf_cnpj=documento)
                    db.session.add(certificado)

                estado_anterior = {
                    "nome_empresa": certificado.nome_empresa,
                    "tipo": certificado.tipo,
                    "data_vencimento": certificado.data_vencimento,
                    "responsavel": certificado.responsavel,
                    "email_contato": certificado.email_contato,
                    "telefone_contato": certificado.telefone_contato,
                    "observacoes": certificado.observacoes,
                    "arquivo_drive_id": certificado.arquivo_drive_id,
                    "ativo": certificado.ativo,
                }
                vencimento_anterior = (
                    certificado.data_vencimento.isoformat()
                    if certificado.data_vencimento
                    else None
                )
                novo_vencimento = converter_data(
                    item.get("vencimento") or item.get("data_vencimento")
                )

                anteriores_mesmo_documento = [
                    anterior
                    for anterior in ativos_por_documento.get(documento, [])
                    if anterior is not certificado
                    and anterior.ativo
                ]
                candidatos_renovados = [
                    anterior
                    for anterior in anteriores_mesmo_documento
                    if anterior.data_vencimento
                    and anterior.data_vencimento < novo_vencimento
                ]
                renovado = bool(
                    novo
                    and not primeira_carga
                    and (
                        candidatos_renovados
                        or (substituir_lista and anteriores_mesmo_documento)
                    )
                )
                if renovado and not candidatos_renovados:
                    candidatos_renovados = anteriores_mesmo_documento
                certificado_anterior = (
                    max(
                        candidatos_renovados,
                        key=lambda anterior: anterior.data_vencimento,
                    )
                    if renovado
                    else None
                )
                arquivo_anterior = (
                    certificado_anterior.arquivo_drive_id
                    if certificado_anterior
                    else certificado.arquivo_drive_id
                )
                vencimento_anterior = (
                    certificado_anterior.data_vencimento.isoformat()
                    if certificado_anterior
                    and certificado_anterior.data_vencimento
                    else vencimento_anterior
                )

                certificado.nome_empresa = nome
                certificado.tipo = "PJ" if len(documento) == 14 else "PF"
                certificado.data_vencimento = novo_vencimento
                certificado.responsavel = (
                    item.get("responsavel") or item.get("socio")
                )
                certificado.email_contato = (
                    item.get("email") or item.get("email_contato")
                )
                certificado.telefone_contato = (
                    item.get("telefone") or item.get("telefone_contato")
                )
                certificado.observacoes = (
                    item.get("observacao") or item.get("observacoes")
                )
                certificado.arquivo_drive_id = arquivo
                certificado.ativo = True
                chaves_recebidas.add((documento, arquivo))

                estado_atual = {
                    "nome_empresa": certificado.nome_empresa,
                    "tipo": certificado.tipo,
                    "data_vencimento": certificado.data_vencimento,
                    "responsavel": certificado.responsavel,
                    "email_contato": certificado.email_contato,
                    "telefone_contato": certificado.telefone_contato,
                    "observacoes": certificado.observacoes,
                    "arquivo_drive_id": certificado.arquivo_drive_id,
                    "ativo": certificado.ativo,
                }
                if novo:
                    resumo["criados"] += 1
                    certificado.data_atualizacao = datetime.now(timezone.utc)
                elif estado_atual != estado_anterior:
                    resumo["atualizados"] += 1
                    certificado.data_atualizacao = datetime.now(timezone.utc)
                else:
                    resumo["inalterados"] += 1

                if renovado:
                    for anterior in candidatos_renovados:
                        anterior.ativo = False
                        anterior.data_atualizacao = datetime.now(timezone.utc)
                        resumo["desativados"] += 1
                    ativos_por_documento[documento] = [certificado]
                elif novo:
                    ativos_por_documento.setdefault(documento, []).append(
                        certificado
                    )

                if novo:
                    if primeira_carga:
                        tipo_alteracao = None
                    else:
                        tipo_alteracao = (
                            "renovado"
                            if renovado
                            else "novo"
                        )
                elif vencimento_anterior != novo_vencimento.isoformat():
                    tipo_alteracao = "vencimento_alterado"
                else:
                    tipo_alteracao = None

                if tipo_alteracao:
                    resumo["alteracoes_certificados"].append(
                        {
                            "tipo": tipo_alteracao,
                            "empresa": nome,
                            "cnpj": documento,
                            "arquivo_anterior": arquivo_anterior,
                            "arquivo_novo": arquivo,
                            "vencimento_anterior": vencimento_anterior,
                            "vencimento_novo": novo_vencimento.isoformat(),
                        }
                    )
            except (ValueError, TypeError) as erro:
                resumo["rejeitados"].append(
                    {"indice": indice, "erro": str(erro)}
                )

        if substituir_lista and chaves_recebidas and not resumo["rejeitados"]:
            for certificado in Certificado.query.filter_by(ativo=True).all():
                chave = (
                    certificado.cpf_cnpj,
                    certificado.arquivo_drive_id or "",
                )
                if chave not in chaves_recebidas:
                    certificado.ativo = False
                    certificado.data_atualizacao = datetime.now(timezone.utc)
                    resumo["desativados"] += 1

        db.session.commit()
        return resumo
    except Exception:
        db.session.rollback()
        raise
