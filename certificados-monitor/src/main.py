import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
RAIZ_REPOSITORIO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if RAIZ_REPOSITORIO not in sys.path:
    sys.path.insert(0, RAIZ_REPOSITORIO)

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path

# Carrega a configuracao antes de importar modulos que resolvem caminhos de storage.
load_dotenv(Path(__file__).resolve().parents[2] / '.env')
load_dotenv()

from config import ErroConfiguracao, carregar_configuracao

try:
    configuracao = carregar_configuracao()
except ErroConfiguracao as erro:
    raise SystemExit(str(erro)) from erro

from src.models.user import db
from src.models.certificado import Certificado
from src.routes.user import user_bp
from src.routes.certificado import certificado_bp
from src.routes.notificacao import notificacao_bp
from src.routes.automacao import automacao_bp
from src.routes.whatscontabil import whatscontabil_bp
from src.routes.relatorio import relatorio_bp
from src.routes.historico import historico_bp
from src.services.notificacao import notificacao_service
from src.services.agendador import agendador_service
from src.services.agendador_automacao import agendador_automacao
from src.caminhos import garantir_pasta, pasta_storage

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
modo_debug = configuracao.debug
app.config['DEBUG'] = modo_debug
app.config['SECRET_KEY'] = configuracao.secret_key
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": configuracao.frontend_origem
        }
    },
)

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(certificado_bp, url_prefix='/api')
app.register_blueprint(notificacao_bp, url_prefix='/api')
app.register_blueprint(automacao_bp, url_prefix='/api')
app.register_blueprint(whatscontabil_bp, url_prefix='/api')
app.register_blueprint(relatorio_bp, url_prefix='/api')
app.register_blueprint(historico_bp, url_prefix='/api')

# Banco local fica em storage/, fora do codigo versionado.
pasta_banco = garantir_pasta(pasta_storage() / 'database')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{pasta_banco / 'app.db'}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()

# Inicializa os serviços
notificacao_service.init_app(app)
agendador_service.init_app(app)
if (
    agendador_automacao.status()['ativo']
    and (not modo_debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true')
):
    agendador_automacao.iniciar_monitoramento()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(
        host=configuracao.host,
        port=configuracao.porta,
        debug=modo_debug,
    )
