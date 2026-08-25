import hmac
import os

from flask import Blueprint, request, jsonify
from datetime import datetime, date, timedelta
from src.models.certificado import db, Certificado
from src.services.sincronizacao import sincronizar_certificados

certificado_bp = Blueprint('certificado', __name__)


def chave_integracao_valida():
    chave_configurada = os.getenv('INTEGRACAO_API_KEY', '').strip()
    chave_recebida = request.headers.get('X-API-Key', '').strip()
    if not chave_configurada:
        return None
    return hmac.compare_digest(chave_configurada, chave_recebida)


@certificado_bp.route('/certificados/sincronizar', methods=['POST'])
def sincronizar_certificados_rota():
    """Recebe em lote os resultados produzidos pela automação."""
    autenticado = chave_integracao_valida()
    if autenticado is None:
        return jsonify({'erro': 'Integração não configurada no servidor'}), 503
    if not autenticado:
        return jsonify({'erro': 'Chave de integração inválida'}), 401

    try:
        dados = request.get_json(silent=True) or {}
        resultado = sincronizar_certificados(
            dados.get('certificados'),
            substituir_lista=dados.get('substituir_lista') is True,
        )
        codigo = 207 if resultado['rejeitados'] else 200
        return jsonify(resultado), codigo
    except ValueError as erro:
        return jsonify({'erro': str(erro)}), 400
    except Exception:
        return jsonify({'erro': 'Falha interna ao sincronizar certificados'}), 500

@certificado_bp.route('/certificados', methods=['GET'])
def listar_certificados():
    """Lista todos os certificados ativos"""
    try:
        certificados = Certificado.query.filter_by(ativo=True).all()
        return jsonify([cert.to_dict() for cert in certificados]), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/<int:id>', methods=['GET'])
def obter_certificado(id):
    """Obtém um certificado específico pelo ID"""
    try:
        certificado = Certificado.query.get_or_404(id)
        return jsonify(certificado.to_dict()), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados', methods=['POST'])
def criar_certificado():
    """Cria um novo certificado"""
    try:
        dados = request.get_json()
        
        # Validação básica
        campos_obrigatorios = ['nome_empresa', 'cpf_cnpj', 'tipo', 'data_vencimento']
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({'erro': f'Campo obrigatório: {campo}'}), 400
        
        # Conversão da data
        try:
            data_vencimento = datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
        
        # Validação do tipo
        if dados['tipo'] not in ['PJ', 'PF']:
            return jsonify({'erro': 'Tipo deve ser PJ ou PF'}), 400
        
        certificado = Certificado(
            nome_empresa=dados['nome_empresa'],
            cpf_cnpj=dados['cpf_cnpj'],
            tipo=dados['tipo'],
            data_vencimento=data_vencimento,
            responsavel=dados.get('responsavel'),
            email_contato=dados.get('email_contato'),
            telefone_contato=dados.get('telefone_contato'),
            observacoes=dados.get('observacoes'),
            arquivo_drive_id=dados.get('arquivo_drive_id')
        )
        
        db.session.add(certificado)
        db.session.commit()
        
        return jsonify(certificado.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/<int:id>', methods=['PUT'])
def atualizar_certificado(id):
    """Atualiza um certificado existente"""
    try:
        certificado = Certificado.query.get_or_404(id)
        dados = request.get_json()
        
        # Atualizar campos se fornecidos
        if 'nome_empresa' in dados:
            certificado.nome_empresa = dados['nome_empresa']
        if 'cpf_cnpj' in dados:
            certificado.cpf_cnpj = dados['cpf_cnpj']
        if 'tipo' in dados:
            if dados['tipo'] not in ['PJ', 'PF']:
                return jsonify({'erro': 'Tipo deve ser PJ ou PF'}), 400
            certificado.tipo = dados['tipo']
        if 'data_vencimento' in dados:
            try:
                certificado.data_vencimento = datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
        if 'responsavel' in dados:
            certificado.responsavel = dados['responsavel']
        if 'email_contato' in dados:
            certificado.email_contato = dados['email_contato']
        if 'telefone_contato' in dados:
            certificado.telefone_contato = dados['telefone_contato']
        if 'observacoes' in dados:
            certificado.observacoes = dados['observacoes']
        if 'arquivo_drive_id' in dados:
            certificado.arquivo_drive_id = dados['arquivo_drive_id']
        
        certificado.data_atualizacao = datetime.utcnow()
        db.session.commit()
        
        return jsonify(certificado.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/<int:id>', methods=['DELETE'])
def deletar_certificado(id):
    """Desativa um certificado (soft delete)"""
    try:
        certificado = Certificado.query.get_or_404(id)
        certificado.ativo = False
        certificado.data_atualizacao = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'mensagem': 'Certificado desativado com sucesso'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/vencendo', methods=['GET'])
def certificados_vencendo():
    """Lista certificados que estão vencendo"""
    try:
        dias = request.args.get('dias', 30, type=int)
        
        certificados = Certificado.query.filter_by(ativo=True).all()
        vencendo = []
        
        for cert in certificados:
            if cert.esta_vencendo(dias):
                cert_dict = cert.to_dict()
                cert_dict['dias_para_vencimento'] = cert.dias_para_vencimento()
                vencendo.append(cert_dict)
        
        # Ordenar por dias para vencimento (mais urgente primeiro)
        vencendo.sort(key=lambda x: x['dias_para_vencimento'])
        
        return jsonify(vencendo), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/vencidos', methods=['GET'])
def certificados_vencidos():
    """Lista certificados que já venceram"""
    try:
        certificados = Certificado.query.filter_by(ativo=True).all()
        vencidos = []
        
        for cert in certificados:
            if cert.esta_vencido():
                cert_dict = cert.to_dict()
                cert_dict['dias_para_vencimento'] = cert.dias_para_vencimento()
                vencidos.append(cert_dict)
        
        # Ordenar por dias vencidos (mais antigo primeiro)
        vencidos.sort(key=lambda x: x['dias_para_vencimento'])
        
        return jsonify(vencidos), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@certificado_bp.route('/certificados/estatisticas', methods=['GET'])
def estatisticas_certificados():
    """Retorna estatísticas dos certificados"""
    try:
        total = Certificado.query.filter_by(ativo=True).count()
        vencendo_30 = len([c for c in Certificado.query.filter_by(ativo=True).all() if c.esta_vencendo(30)])
        vencendo_15 = len([c for c in Certificado.query.filter_by(ativo=True).all() if c.esta_vencendo(15)])
        vencidos = len([c for c in Certificado.query.filter_by(ativo=True).all() if c.esta_vencido()])
        
        pj_count = Certificado.query.filter_by(ativo=True, tipo='PJ').count()
        pf_count = Certificado.query.filter_by(ativo=True, tipo='PF').count()
        
        return jsonify({
            'total': total,
            'vencendo_30_dias': vencendo_30,
            'vencendo_15_dias': vencendo_15,
            'vencidos': vencidos,
            'pessoa_juridica': pj_count,
            'pessoa_fisica': pf_count
        }), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

