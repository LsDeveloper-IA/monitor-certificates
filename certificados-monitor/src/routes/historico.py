import hmac
import io
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from src.models.certificado import Certificado, db

historico_bp = Blueprint('historico', __name__)


class RegistroCertificado(db.Model):
    __tablename__ = 'registro_certificado'
    id = db.Column(db.Integer, primary_key=True)
    certificado_id = db.Column(db.Integer, db.ForeignKey('certificado.id'), nullable=False, index=True)
    autor = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    imagens = db.relationship('ImagemRegistro', cascade='all, delete-orphan', lazy='select')
    edicao = db.relationship('EdicaoRegistro', cascade='all, delete-orphan', uselist=False)


class EdicaoRegistro(db.Model):
    __tablename__ = 'edicao_registro'
    registro_id = db.Column(db.Integer, db.ForeignKey('registro_certificado.id'), primary_key=True)
    atualizado_em = db.Column(db.DateTime, nullable=False)


class ImagemRegistro(db.Model):
    __tablename__ = 'imagem_registro'
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey('registro_certificado.id'), nullable=False, index=True)
    conteudo = db.deferred(db.Column(db.LargeBinary, nullable=False))


@historico_bp.before_request
def proteger():
    chave = os.getenv('AUTOMACAO_EXECUTION_KEY', '').strip()
    if request.remote_addr not in {'127.0.0.1', '::1'} or not chave or not hmac.compare_digest(chave.encode(), request.headers.get('X-Automation-Key', '').encode()):
        return jsonify(erro='Acesso nao autorizado'), 401
    if request.content_length and request.content_length > 16 * 1024 * 1024:
        return jsonify(erro='Os anexos excedem o limite de 15 MB.'), 413


@historico_bp.route('/historico/certificados/<int:certificado_id>', methods=['GET', 'POST'])
def registros(certificado_id):
    db.get_or_404(Certificado, certificado_id)
    if request.method == 'GET':
        pagina = max(1, request.args.get('pagina', 1, type=int))
        consulta = RegistroCertificado.query.filter_by(certificado_id=certificado_id).order_by(RegistroCertificado.id.desc())
        itens = consulta.offset((pagina - 1) * 20).limit(21).all()
        return jsonify(registros=[{
            'id': r.id, 'autor': r.autor, 'texto': r.texto,
            'criado_em': r.criado_em.replace(tzinfo=timezone.utc).isoformat(),
            'editado_em': r.edicao.atualizado_em.replace(tzinfo=timezone.utc).isoformat() if r.edicao else None,
            'imagens': [i.id for i in r.imagens],
        } for r in itens[:20]], tem_mais=len(itens) > 20)
    autor = request.form.get('autor', '').strip()
    texto = request.form.get('texto', '').strip()
    arquivos = request.files.getlist('imagens')
    if not autor or len(autor) > 100 or not texto or len(texto) > 5000:
        return jsonify(erro='Informe seu nome (ate 100 caracteres) e a observacao (ate 5000).'), 400
    if len(arquivos) > 3:
        return jsonify(erro='Anexe no maximo 3 imagens por registro.'), 400
    imagens = []
    try:
        for arquivo in arquivos:
            dados = arquivo.read(5 * 1024 * 1024 + 1)
            if len(dados) > 5 * 1024 * 1024:
                return jsonify(erro='Cada imagem deve ter no maximo 5 MB.'), 400
            with Image.open(io.BytesIO(dados)) as img:
                if img.format not in {'JPEG', 'PNG', 'WEBP'} or img.width * img.height > 16_000_000:
                    return jsonify(erro='Use imagens JPG, PNG ou WebP de ate 16 megapixels.'), 400
                img.load()
                img.thumbnail((2000, 2000))
                saida = io.BytesIO()
                img.convert('RGB').save(saida, format='JPEG', quality=85)
                imagens.append(ImagemRegistro(conteudo=saida.getvalue()))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return jsonify(erro='Uma das imagens esta invalida. Remova ou substitua o arquivo.'), 400
    registro = RegistroCertificado(certificado_id=certificado_id, autor=autor, texto=texto, imagens=imagens)
    try:
        db.session.add(registro)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(erro='Nao foi possivel salvar. Tente novamente.'), 500
    return jsonify(id=registro.id), 201


@historico_bp.route('/historico/registros/<int:registro_id>', methods=['PUT', 'DELETE'])
def alterar_registro(registro_id):
    registro = db.get_or_404(RegistroCertificado, registro_id)
    if request.method == 'PUT':
        dados = request.get_json(silent=True)
        texto = dados.get('texto') if isinstance(dados, dict) else None
        if not isinstance(texto, str) or not texto.strip() or len(texto.strip()) > 5000:
            return jsonify(erro='Informe uma observacao de ate 5000 caracteres.'), 400
        registro.texto = texto.strip()
        if not registro.edicao:
            registro.edicao = EdicaoRegistro()
        registro.edicao.atualizado_em = datetime.now(timezone.utc)
    else:
        db.session.delete(registro)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(erro='Nao foi possivel alterar o registro. Tente novamente.'), 500
    return jsonify(ok=True)


@historico_bp.route('/historico/imagens/<int:imagem_id>')
def imagem(imagem_id):
    item = db.get_or_404(ImagemRegistro, imagem_id)
    resposta = send_file(io.BytesIO(item.conteudo), mimetype='image/jpeg', download_name=f'imagem-{item.id}.jpg')
    resposta.headers['Cache-Control'] = 'private, no-store'
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    return resposta
