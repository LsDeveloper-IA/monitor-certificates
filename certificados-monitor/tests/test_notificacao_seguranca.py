import os
import unittest
from unittest.mock import patch

from flask import Flask

from src.routes.notificacao import notificacao_bp


class NotificacaoProtegidaTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["AUTOMACAO_EXECUTION_KEY"] = "chave-interna-teste"
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(notificacao_bp, url_prefix="/api")
        self.cliente = app.test_client()

    def tearDown(self):
        os.environ.pop("AUTOMACAO_EXECUTION_KEY", None)

    def test_bloqueia_rota_sem_chave(self):
        resposta = self.cliente.get("/api/notificacao/agendador/status")
        self.assertEqual(resposta.status_code, 401)

    @patch("src.routes.notificacao.agendador_service.status", return_value={})
    def test_permite_rota_local_com_chave(self, _status):
        resposta = self.cliente.get(
            "/api/notificacao/agendador/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )
        self.assertEqual(resposta.status_code, 200)

    def test_bloqueia_origem_remota_mesmo_com_chave(self):
        resposta = self.cliente.get(
            "/api/notificacao/agendador/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )
        self.assertEqual(resposta.status_code, 401)


if __name__ == "__main__":
    unittest.main()
