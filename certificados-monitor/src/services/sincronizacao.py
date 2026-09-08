import re
from datetime import datetime

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
    documentos_anteriores = {item.cpf_cnpj for item in certificados_anteriores}

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

                vencimento_anterior = (
                    certificado.data_vencimento.isoformat()
                    if certificado.data_vencimento
                    else None
                )
                arquivo_anterior = certificado.arquivo_drive_id
                novo_vencimento = converter_data(
                    item.get("vencimento") or item.get("data_vencimento")
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
                certificado.data_atualizacao = datetime.utcnow()
                chaves_recebidas.add((documento, arquivo))
                resumo["criados" if novo else "atualizados"] += 1

                if novo:
                    if primeira_carga:
                        tipo_alteracao = None
                    else:
                        tipo_alteracao = (
                            "renovado"
                            if documento in documentos_anteriores
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
                else:
                    resumo["inalterados"] += 1
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
                    certificado.data_atualizacao = datetime.utcnow()
                    resumo["desativados"] += 1

        db.session.commit()
        return resumo
    except Exception:
        db.session.rollback()
        raise
