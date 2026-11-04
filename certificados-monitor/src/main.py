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

from src.caminhos import pasta_aplicacao

# Carrega a configuracao antes de importar modulos que resolvem caminhos de storage.
load_dotenv(pasta_aplicacao() / '.env')
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
from src.routes.configuracao_local import configuracao_local_bp
from src.services.notificacao import notificacao_service
from src.services.agendador import agendador_service
from src.services.agendador_automacao import agendador_automacao
from src.caminhos import garantir_pasta, pasta_storage


def _pasta_web():
    """Localiza o frontend estatico no repositorio ou no executavel."""
    configurada = os.getenv('MONITOR_WEB_DIR', '').strip()
    if configurada:
        return configurada
    if getattr(sys, 'frozen', False):
        return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'web')
    return os.path.join(os.path.dirname(__file__), 'static')


app = Flask(__name__, static_folder=_pasta_web())
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
app.register_blueprint(configuracao_local_bp, url_prefix='/api')

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

    raiz = Path(static_folder_path).resolve()
    if path:
        candidato = (raiz / path).resolve()
        if candidato != raiz and raiz not in candidato.parents:
            return "Not found", 404
        if candidato.is_file():
            return send_from_directory(static_folder_path, path)
        pagina = candidato / 'index.html'
        if pagina.is_file():
            return send_from_directory(
                static_folder_path,
                str(Path(path) / 'index.html'),
            )
        pagina_html = candidato.with_suffix('.html')
        if pagina_html.is_file():
            return send_from_directory(
                static_folder_path,
                str(Path(path).with_suffix('.html')),
            )

    index_path = raiz / 'index.html'
    if index_path.is_file():
        return send_from_directory(static_folder_path, 'index.html')
    return "index.html not found", 404


if __name__ == '__main__':
    app.run(
        host=configuracao.host,
        port=configuracao.porta,
        debug=modo_debug,
    )
