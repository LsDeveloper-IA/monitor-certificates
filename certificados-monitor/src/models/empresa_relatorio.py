from datetime import datetime

from src.models.user import db


class EmpresaRelatorio(db.Model):
    __tablename__ = "empresas_relatorio"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(220), unique=True, nullable=False, index=True)
    cnpj = db.Column(db.String(18), nullable=True)
    nome = db.Column(db.String(250), nullable=False)
    motivo = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(10), nullable=False, index=True)
    primeira_ocorrencia = db.Column(db.String(40), nullable=True)
    ultima_ocorrencia = db.Column(db.String(40), nullable=True)
    primeiro_arquivo = db.Column(db.String(250), nullable=True)
    ultimo_arquivo = db.Column(db.String(250), nullable=True)
    ocorrencias = db.Column(db.Integer, nullable=False, default=1)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self):
        return {
            "cnpj": self.cnpj or "",
            "nome": self.nome,
            "motivo": self.motivo,
            "status": self.status,
            "primeira_ocorrencia": self.primeira_ocorrencia,
            "ultima_ocorrencia": self.ultima_ocorrencia,
            "ocorrencias": self.ocorrencias,
        }


class RelatorioDriveProcessado(db.Model):
    __tablename__ = "relatorios_drive_processados"

    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(260), unique=True, nullable=False, index=True)
    arquivo_id = db.Column(db.String(150), nullable=True)
    arquivo_nome = db.Column(db.String(250), nullable=True)
    arquivo_modificado_em = db.Column(db.String(40), nullable=True)
    titulo = db.Column(db.String(250), nullable=True)
    executado_em = db.Column(db.String(40), nullable=True)
    total_sucessos = db.Column(db.Integer, nullable=False, default=0)
    total_ignorados = db.Column(db.Integer, nullable=False, default=0)
    total_falhas = db.Column(db.Integer, nullable=False, default=0)
    processado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
