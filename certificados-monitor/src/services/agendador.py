import schedule
import time
import threading
from datetime import datetime
from src.services.notificacao import notificacao_service
from src.models.certificado import Certificado

class AgendadorService:
    def __init__(self, app=None):
        self.app = app
        self.executando = False
        self.thread_agendador = None
        self.emails_destino = []
        self.telefones_destino = []
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa o serviço com as configurações do Flask"""
        self.emails_destino = app.config.get('EMAILS_ALERTA', [])
        self.telefones_destino = app.config.get('TELEFONES_ALERTA', [])
    
    def configurar_destinatarios(self, emails: list, telefones: list = None):
        """Configura os destinatários dos alertas"""
        self.emails_destino = emails or []
        self.telefones_destino = telefones or []
    
    def verificar_certificados_job(self):
        """Job que verifica certificados e envia notificações"""
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando verificação de certificados...")
            
            if not self.emails_destino:
                print("Nenhum e-mail de destino configurado. Pulando verificação.")
                return
            
            # Usa o contexto da aplicação Flask
            with self.app.app_context():
                resultado = notificacao_service.verificar_e_notificar_vencimentos(
                    self.emails_destino, 
                    self.telefones_destino
                )
                
                print(f"Verificação concluída:")
                print(f"  - Certificados vencendo em 30 dias: {len(resultado['certificados_30_dias'])}")
                print(f"  - Certificados vencendo em 15 dias: {len(resultado['certificados_15_dias'])}")
                print(f"  - E-mails enviados: {resultado['emails_enviados']}")
                print(f"  - WhatsApp enviados: {resultado['whatsapp_enviados']}")
                
                if resultado['erros']:
                    print(f"  - Erros: {len(resultado['erros'])}")
                    for erro in resultado['erros']:
                        print(f"    * {erro}")
                
        except Exception as e:
            print(f"Erro na verificação de certificados: {e}")
    
    def agendar_verificacoes(self):
        """Agenda as verificações diárias"""
        # Verifica todos os dias às 9:00
        schedule.every().day.at("09:00").do(self.verificar_certificados_job)
        
        # Verifica também às 14:00 para certificados mais urgentes (15 dias)
        schedule.every().day.at("14:00").do(self.verificar_certificados_urgentes)
        
        print("Verificações agendadas:")
        print("  - 09:00: Verificação completa (30 e 15 dias)")
        print("  - 14:00: Verificação urgente (15 dias)")
    
    def verificar_certificados_urgentes(self):
        """Job específico para certificados urgentes (15 dias)"""
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificação urgente de certificados...")
            
            if not self.emails_destino:
                print("Nenhum e-mail de destino configurado. Pulando verificação.")
                return
            
            with self.app.app_context():
                # Busca apenas certificados vencendo em 15 dias
                certificados_urgentes = []
                todos_certificados = Certificado.query.filter_by(ativo=True).all()
                
                for cert in todos_certificados:
                    if cert.esta_vencendo(15):
                        certificados_urgentes.append(cert)
                
                if certificados_urgentes:
                    texto, html = notificacao_service.gerar_mensagem_vencimento(certificados_urgentes, 15)
                    
                    emails_enviados = 0
                    whatsapp_enviados = 0
                    
                    for email in self.emails_destino:
                        if notificacao_service.enviar_email(email, "🚨 URGENTE - Certificados Vencendo em 15 Dias", texto, html):
                            emails_enviados += 1
                    
                    if self.telefones_destino:
                        for telefone in self.telefones_destino:
                            if notificacao_service.enviar_whatsapp(telefone, texto):
                                whatsapp_enviados += 1
                    
                    print(f"Verificação urgente concluída:")
                    print(f"  - Certificados urgentes: {len(certificados_urgentes)}")
                    print(f"  - E-mails enviados: {emails_enviados}")
                    print(f"  - WhatsApp enviados: {whatsapp_enviados}")
                else:
                    print("Nenhum certificado urgente encontrado.")
                
        except Exception as e:
            print(f"Erro na verificação urgente: {e}")
    
    def executar_agendador(self):
        """Executa o loop do agendador em thread separada"""
        while self.executando:
            schedule.run_pending()
            time.sleep(60)  # Verifica a cada minuto
    
    def iniciar(self):
        """Inicia o serviço de agendamento"""
        if self.executando:
            print("Agendador já está executando.")
            return
        
        self.executando = True
        self.agendar_verificacoes()
        
        # Inicia thread do agendador
        self.thread_agendador = threading.Thread(target=self.executar_agendador, daemon=True)
        self.thread_agendador.start()
        
        print("Serviço de agendamento iniciado.")
    
    def parar(self):
        """Para o serviço de agendamento"""
        self.executando = False
        if self.thread_agendador and self.thread_agendador.is_alive():
            self.thread_agendador.join(timeout=5)
        
        schedule.clear()
        print("Serviço de agendamento parado.")
    
    def verificar_agora(self):
        """Executa verificação imediata (para testes)"""
        print("Executando verificação imediata...")
        self.verificar_certificados_job()
    
    def status(self):
        """Retorna o status do agendador"""
        return {
            'executando': self.executando,
            'proximas_execucoes': [str(job.next_run) for job in schedule.jobs],
            'emails_configurados': len(self.emails_destino),
            'telefones_configurados': len(self.telefones_destino)
        }

# Instância global do serviço
agendador_service = AgendadorService()

