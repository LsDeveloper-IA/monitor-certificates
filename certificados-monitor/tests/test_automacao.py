import os
import unittest

from flask import Flask

from src.routes.automacao import automacao_bp


class AutomacaoProtegidaTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["AUTOMACAO_EXECUTION_KEY"] = "chave-interna-teste"
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(automacao_bp, url_prefix="/api")
        self.cliente = app.test_client()

    def tearDown(self):
        os.environ.pop("AUTOMACAO_EXECUTION_KEY", None)

    def test_bloqueia_status_sem_chave(self):
        resposta = self.cliente.get("/api/automacao/status")
        self.assertEqual(resposta.status_code, 401)

    def test_permite_status_local_com_chave(self):
        resposta = self.cliente.get(
            "/api/automacao/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("executando", resposta.json)

    def test_bloqueia_origem_remota(self):
        resposta = self.cliente.get(
            "/api/automacao/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )
        self.assertEqual(resposta.status_code, 401)


if __name__ == "__main__":
    unittest.main()
