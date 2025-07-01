from flask import Blueprint, request, jsonify
from src.services.notificacao import notificacao_service
from src.services.agendador import agendador_service

notificacao_bp = Blueprint('notificacao', __name__)

@notificacao_bp.route('/notificacao/configurar-email', methods=['POST'])
def configurar_email():
    """Configura as credenciais de e-mail"""
    try:
        dados = request.get_json()
        
        campos_obrigatorios = ['smtp_server', 'smtp_port', 'usuario', 'senha']
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({'erro': f'Campo obrigatório: {campo}'}), 400
        
        notificacao_service.configurar_email(
            dados['smtp_server'],
            int(dados['smtp_port']),
            dados['usuario'],
            dados['senha']
        )
        
        return jsonify({'mensagem': 'Configurações de e-mail salvas com sucesso'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/configurar-whatsapp', methods=['POST'])
def configurar_whatsapp():
    """Configura as credenciais do WhatsApp"""
    try:
        dados = request.get_json()
        
        campos_obrigatorios = ['token', 'phone_id']
        for campo in campos_obrigatorios:
            if campo not in dados:
                return jsonify({'erro': f'Campo obrigatório: {campo}'}), 400
        
        notificacao_service.configurar_whatsapp(
            dados['token'],
            dados['phone_id']
        )
        
        return jsonify({'mensagem': 'Configurações do WhatsApp salvas com sucesso'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/configurar-destinatarios', methods=['POST'])
def configurar_destinatarios():
    """Configura os destinatários das notificações"""
    try:
        dados = request.get_json()
        
        emails = dados.get('emails', [])
        telefones = dados.get('telefones', [])
        
        if not emails:
            return jsonify({'erro': 'Pelo menos um e-mail deve ser configurado'}), 400
        
        agendador_service.configurar_destinatarios(emails, telefones)
        
        return jsonify({
            'mensagem': 'Destinatários configurados com sucesso',
            'emails': len(emails),
            'telefones': len(telefones)
        }), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/teste-email', methods=['POST'])
def teste_email():
    """Envia um e-mail de teste"""
    try:
        dados = request.get_json()
        
        if 'destinatario' not in dados:
            return jsonify({'erro': 'Campo obrigatório: destinatario'}), 400
        
        assunto = "Teste - Sistema de Monitoramento de Certificados"
        corpo = """Este é um e-mail de teste do Sistema de Monitoramento de Certificados Digitais.

Se você recebeu esta mensagem, significa que as configurações de e-mail estão funcionando corretamente.

Sistema desenvolvido para automatizar o controle de vencimento de certificados digitais.
        """
        
        corpo_html = """
        <html>
        <body>
            <h2 style="color: #2e7d32;">✅ Teste do Sistema de Monitoramento</h2>
            <p>Este é um e-mail de teste do <strong>Sistema de Monitoramento de Certificados Digitais</strong>.</p>
            
            <p>Se você recebeu esta mensagem, significa que as configurações de e-mail estão funcionando corretamente.</p>
            
            <div style="background-color: #e8f5e8; padding: 15px; border-left: 4px solid #4caf50; margin: 20px 0;">
                <p><strong>✓ Configuração de e-mail: OK</strong></p>
                <p><strong>✓ Conexão SMTP: OK</strong></p>
                <p><strong>✓ Envio de mensagens: OK</strong></p>
            </div>
            
            <hr>
            <p style="font-size: 12px; color: #666;">
                Sistema desenvolvido para automatizar o controle de vencimento de certificados digitais.<br>
                Data/Hora do teste: """ + f"{dados.get('timestamp', 'N/A')}" + """
            </p>
        </body>
        </html>
        """
        
        sucesso = notificacao_service.enviar_email(
            dados['destinatario'], 
            assunto, 
            corpo, 
            corpo_html
        )
        
        if sucesso:
            return jsonify({'mensagem': 'E-mail de teste enviado com sucesso'}), 200
        else:
            return jsonify({'erro': 'Falha ao enviar e-mail de teste'}), 500
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/teste-whatsapp', methods=['POST'])
def teste_whatsapp():
    """Envia uma mensagem de teste via WhatsApp"""
    try:
        dados = request.get_json()
        
        if 'numero' not in dados:
            return jsonify({'erro': 'Campo obrigatório: numero'}), 400
        
        mensagem = """🤖 *Teste - Sistema de Monitoramento de Certificados*

Este é um teste do Sistema de Monitoramento de Certificados Digitais.

Se você recebeu esta mensagem, significa que as configurações do WhatsApp estão funcionando corretamente.

✅ Configuração WhatsApp: OK
✅ API Business: OK  
✅ Envio de mensagens: OK

Sistema desenvolvido para automatizar o controle de vencimento de certificados digitais."""
        
        sucesso = notificacao_service.enviar_whatsapp(dados['numero'], mensagem)
        
        if sucesso:
            return jsonify({'mensagem': 'Mensagem de teste enviada com sucesso'}), 200
        else:
            return jsonify({'erro': 'Falha ao enviar mensagem de teste'}), 500
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/verificar-agora', methods=['POST'])
def verificar_agora():
    """Executa verificação imediata de certificados"""
    try:
        dados = request.get_json() or {}
        emails = dados.get('emails', [])
        telefones = dados.get('telefones', [])
        
        if not emails:
            return jsonify({'erro': 'Pelo menos um e-mail deve ser fornecido'}), 400
        
        resultado = notificacao_service.verificar_e_notificar_vencimentos(emails, telefones)
        
        return jsonify({
            'mensagem': 'Verificação executada com sucesso',
            'resultado': resultado
        }), 200
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/agendador/status', methods=['GET'])
def status_agendador():
    """Retorna o status do agendador"""
    try:
        status = agendador_service.status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/agendador/iniciar', methods=['POST'])
def iniciar_agendador():
    """Inicia o serviço de agendamento"""
    try:
        agendador_service.iniciar()
        return jsonify({'mensagem': 'Agendador iniciado com sucesso'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/agendador/parar', methods=['POST'])
def parar_agendador():
    """Para o serviço de agendamento"""
    try:
        agendador_service.parar()
        return jsonify({'mensagem': 'Agendador parado com sucesso'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@notificacao_bp.route('/notificacao/preview', methods=['GET'])
def preview_notificacao():
    """Gera preview da mensagem de notificação"""
    try:
        dias = request.args.get('dias', 30, type=int)
        
        # Busca certificados vencendo
        from src.models.certificado import Certificado
        certificados = []
        todos_certificados = Certificado.query.filter_by(ativo=True).all()
        
        for cert in todos_certificados:
            if cert.esta_vencendo(dias):
                certificados.append(cert)
        
        if not certificados:
            return jsonify({
                'mensagem': f'Nenhum certificado vencendo em {dias} dias',
                'texto': '',
                'html': ''
            }), 200
        
        texto, html = notificacao_service.gerar_mensagem_vencimento(certificados, dias)
        
        return jsonify({
            'certificados_encontrados': len(certificados),
            'texto': texto,
            'html': html
        }), 200
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

