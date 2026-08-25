from src.models.user import db
from datetime import datetime, date

class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_empresa = db.Column(db.String(200), nullable=False)
    cpf_cnpj = db.Column(db.String(18), nullable=False)
    tipo = db.Column(db.String(2), nullable=False)  # 'PJ' ou 'PF'
    data_vencimento = db.Column(db.Date, nullable=False)
    responsavel = db.Column(db.String(100), nullable=True)
    email_contato = db.Column(db.String(120), nullable=True)
    telefone_contato = db.Column(db.String(20), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    arquivo_drive_id = db.Column(db.String(100), nullable=True)  # ID do arquivo no Google Drive
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Certificado {self.nome_empresa} - {self.cpf_cnpj}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nome_empresa': self.nome_empresa,
            'cpf_cnpj': self.cpf_cnpj,
            'tipo': self.tipo,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'responsavel': self.responsavel,
            'email_contato': self.email_contato,
            'telefone_contato': self.telefone_contato,
            'observacoes': self.observacoes,
            'arquivo_drive_id': self.arquivo_drive_id,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
            'ativo': self.ativo,
            'dias_para_vencimento': self.dias_para_vencimento(),
            'status': self.status_vencimento()
        }

    def status_vencimento(self):
        dias = self.dias_para_vencimento()
        if dias is None:
            return 'SEM DATA'
        if dias < 0:
            return 'VENCIDO'
        if dias <= 15:
            return 'URGENTE'
        if dias <= 30:
            return 'VENCE EM BREVE'
        return 'EM DIA'

    def dias_para_vencimento(self):
        """Retorna o número de dias até o vencimento do certificado"""
        if self.data_vencimento:
            hoje = date.today()
            delta = self.data_vencimento - hoje
            return delta.days
        return None

    def esta_vencendo(self, dias=30):
        """Verifica se o certificado está vencendo dentro do número de dias especificado"""
        dias_restantes = self.dias_para_vencimento()
        if dias_restantes is not None:
            return 0 <= dias_restantes <= dias
        return False

    def esta_vencido(self):
        """Verifica se o certificado já venceu"""
        dias_restantes = self.dias_para_vencimento()
        if dias_restantes is not None:
            return dias_restantes < 0
        return False

