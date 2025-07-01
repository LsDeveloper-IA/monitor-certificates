import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
import requests
import json
from typing import List, Dict, Optional
from src.models.certificado import Certificado

class NotificacaoService:
    def __init__(self, app=None):
        self.app = app
        self.smtp_server = None
        self.smtp_port = None
        self.email_usuario = None
        self.email_senha = None
        self.whatsapp_token = None
        self.whatsapp_phone_id = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa o serviço com as configurações do Flask"""
        self.smtp_server = app.config.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = app.config.get('SMTP_PORT', 587)
        self.email_usuario = app.config.get('EMAIL_USUARIO')
        self.email_senha = app.config.get('EMAIL_SENHA')
        self.whatsapp_token = app.config.get('WHATSAPP_TOKEN')
        self.whatsapp_phone_id = app.config.get('WHATSAPP_PHONE_ID')
    
    def configurar_email(self, smtp_server: str, smtp_port: int, usuario: str, senha: str):
        """Configura as credenciais de e-mail"""
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_usuario = usuario
        self.email_senha = senha
    
    def configurar_whatsapp(self, token: str, phone_id: str):
        """Configura as credenciais do WhatsApp Business API"""
        self.whatsapp_token = token
        self.whatsapp_phone_id = phone_id
    
    def enviar_email(self, destinatario: str, assunto: str, corpo: str, corpo_html: str = None) -> bool:
        """Envia um e-mail"""
        try:
            if not all([self.smtp_server, self.smtp_port, self.email_usuario, self.email_senha]):
                raise ValueError("Configurações de e-mail não definidas")
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = assunto
            msg['From'] = self.email_usuario
            msg['To'] = destinatario
            
            # Adiciona texto simples
            part1 = MIMEText(corpo, 'plain', 'utf-8')
            msg.attach(part1)
            
            # Adiciona HTML se fornecido
            if corpo_html:
                part2 = MIMEText(corpo_html, 'html', 'utf-8')
                msg.attach(part2)
            
            # Conecta ao servidor SMTP e envia
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_usuario, self.email_senha)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Erro ao enviar e-mail: {e}")
            return False
    
    def enviar_whatsapp(self, numero: str, mensagem: str) -> bool:
        """Envia mensagem via WhatsApp Business API"""
        try:
            if not all([self.whatsapp_token, self.whatsapp_phone_id]):
                print("Configurações do WhatsApp não definidas")
                return False
            
            # Remove caracteres não numéricos do número
            numero_limpo = ''.join(filter(str.isdigit, numero))
            
            # Adiciona código do país se não tiver
            if not numero_limpo.startswith('55'):
                numero_limpo = '55' + numero_limpo
            
            url = f"https://graph.facebook.com/v17.0/{self.whatsapp_phone_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.whatsapp_token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": numero_limpo,
                "type": "text",
                "text": {
                    "body": mensagem
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return True
            else:
                print(f"Erro ao enviar WhatsApp: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Erro ao enviar WhatsApp: {e}")
            return False
    
    def gerar_mensagem_vencimento(self, certificados: List[Certificado], dias: int) -> tuple:
        """Gera mensagem de alerta de vencimento"""
        if not certificados:
            return "", ""
        
        # Texto simples
        texto = f"🚨 ALERTA DE CERTIFICADOS DIGITAIS - {dias} DIAS PARA VENCIMENTO\\n\\n"
        
        for cert in certificados:
            dias_restantes = cert.dias_para_vencimento()
            texto += f"📋 {cert.nome_empresa}\\n"
            texto += f"📄 {cert.cpf_cnpj} ({cert.tipo})\\n"
            texto += f"📅 Vence em: {cert.data_vencimento.strftime('%d/%m/%Y')} ({dias_restantes} dias)\\n"
            if cert.responsavel:
                texto += f"👤 Responsável: {cert.responsavel}\\n"
            if cert.telefone_contato:
                texto += f"📞 Telefone: {cert.telefone_contato}\\n"
            texto += "\\n" + "-"*50 + "\\n\\n"
        
        texto += "⚠️ Entre em contato com os clientes para renovação dos certificados!\\n"
        texto += f"📊 Total de certificados alertados: {len(certificados)}"
        
        # HTML
        html = f"""
        <html>
        <body>
            <h2 style="color: #d32f2f;">🚨 ALERTA DE CERTIFICADOS DIGITAIS</h2>
            <p><strong>{dias} DIAS PARA VENCIMENTO</strong></p>
            
            <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <thead style="background-color: #f5f5f5;">
                    <tr>
                        <th>Nome/Empresa</th>
                        <th>CPF/CNPJ</th>
                        <th>Tipo</th>
                        <th>Vencimento</th>
                        <th>Dias Restantes</th>
                        <th>Responsável</th>
                        <th>Contato</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for cert in certificados:
            dias_restantes = cert.dias_para_vencimento()
            cor_linha = "#ffebee" if dias_restantes <= 15 else "#fff3e0"
            
            html += f"""
                    <tr style="background-color: {cor_linha};">
                        <td>{cert.nome_empresa}</td>
                        <td>{cert.cpf_cnpj}</td>
                        <td>{cert.tipo}</td>
                        <td>{cert.data_vencimento.strftime('%d/%m/%Y')}</td>
                        <td style="font-weight: bold; color: {'#d32f2f' if dias_restantes <= 15 else '#f57c00'};">{dias_restantes} dias</td>
                        <td>{cert.responsavel or '-'}</td>
                        <td>{cert.telefone_contato or cert.email_contato or '-'}</td>
                    </tr>
            """
        
        html += f"""
                </tbody>
            </table>
            
            <p style="margin-top: 20px;">
                <strong>⚠️ Entre em contato com os clientes para renovação dos certificados!</strong>
            </p>
            <p>
                📊 <strong>Total de certificados alertados: {len(certificados)}</strong>
            </p>
            
            <hr>
            <p style="font-size: 12px; color: #666;">
                Mensagem gerada automaticamente pelo Sistema de Monitoramento de Certificados Digitais<br>
                Data/Hora: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
            </p>
        </body>
        </html>
        """
        
        return texto, html
    
    def verificar_e_notificar_vencimentos(self, emails_destino: List[str], telefones_destino: List[str] = None) -> Dict:
        """Verifica certificados vencendo e envia notificações"""
        resultado = {
            'certificados_30_dias': [],
            'certificados_15_dias': [],
            'emails_enviados': 0,
            'whatsapp_enviados': 0,
            'erros': []
        }
        
        try:
            # Busca certificados vencendo em 30 dias
            certificados_30 = []
            certificados_15 = []
            
            todos_certificados = Certificado.query.filter_by(ativo=True).all()
            
            for cert in todos_certificados:
                if cert.esta_vencendo(30):
                    resultado['certificados_30_dias'].append(cert.to_dict())
                    certificados_30.append(cert)
                    
                if cert.esta_vencendo(15):
                    resultado['certificados_15_dias'].append(cert.to_dict())
                    certificados_15.append(cert)
            
            # Envia alertas para 30 dias
            if certificados_30:
                texto, html = self.gerar_mensagem_vencimento(certificados_30, 30)
                
                for email in emails_destino:
                    if self.enviar_email(email, "🚨 Certificados Vencendo em 30 Dias", texto, html):
                        resultado['emails_enviados'] += 1
                    else:
                        resultado['erros'].append(f"Falha ao enviar e-mail para {email}")
                
                if telefones_destino:
                    for telefone in telefones_destino:
                        if self.enviar_whatsapp(telefone, texto):
                            resultado['whatsapp_enviados'] += 1
                        else:
                            resultado['erros'].append(f"Falha ao enviar WhatsApp para {telefone}")
            
            # Envia alertas específicos para 15 dias (mais urgente)
            if certificados_15:
                texto, html = self.gerar_mensagem_vencimento(certificados_15, 15)
                
                for email in emails_destino:
                    if self.enviar_email(email, "🚨 URGENTE - Certificados Vencendo em 15 Dias", texto, html):
                        resultado['emails_enviados'] += 1
                    else:
                        resultado['erros'].append(f"Falha ao enviar e-mail urgente para {email}")
        
        except Exception as e:
            resultado['erros'].append(f"Erro geral: {str(e)}")
        
        return resultado

# Instância global do serviço
notificacao_service = NotificacaoService()

