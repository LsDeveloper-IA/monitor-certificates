import os
import unittest
from unittest.mock import patch

from flask import Flask

from src.routes.whatscontabil import whatscontabil_bp


class WhatsContabilProtegidaTestCase(unittest.TestCase):
    def setUp(self):
        os.environ.update({
            "AUTOMACAO_EXECUTION_KEY": "chave-interna-teste",
            "WHATSCONTABIL_URL": "https://whatscontabil.example",
            "WHATSCONTABIL_TOKEN": "token-de-teste",
            "MODO_WHATSCONTABIL": "teste",
            "WHATSCONTABIL_NUMERO_TESTE": "5585999999999",
            "WHATSCONTABIL_WHATSAPP_ID": "2",
        })
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(whatscontabil_bp, url_prefix="/api")
        self.cliente = app.test_client()
        self.headers = {"X-Automation-Key": "chave-interna-teste"}

    def tearDown(self):
        for nome in (
            "AUTOMACAO_EXECUTION_KEY",
            "WHATSCONTABIL_URL",
            "WHATSCONTABIL_TOKEN",
            "MODO_WHATSCONTABIL",
            "WHATSCONTABIL_NUMERO_TESTE",
            "WHATSCONTABIL_WHATSAPP_ID",
        ):
            os.environ.pop(nome, None)

    def test_status_nao_expoe_token(self):
        resposta = self.cliente.get("/api/whatscontabil/status", headers=self.headers)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json["token_configurado"])
        self.assertNotIn("token", resposta.json)
        self.assertEqual(resposta.json["numero_teste"], "***9999")

    def test_bloqueia_sem_chave(self):
        resposta = self.cliente.get("/api/whatscontabil/status")
        self.assertEqual(resposta.status_code, 401)

    @patch("src.routes.whatscontabil.listar_templates", return_value=[{"id": 1}])
    @patch("src.routes.whatscontabil.obter_conexao_oficial")
    @patch("src.routes.whatscontabil.listar_conexoes")
    def test_valida_sem_enviar_mensagem(self, listar, obter, _templates):
        conexao = {"id": 2, "name": "Oficial", "status": "CONNECTED", "isOfficial": 1}
        listar.return_value = [conexao]
        obter.return_value = conexao

        resposta = self.cliente.post("/api/whatscontabil/validar", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json["conectado"])
        self.assertEqual(resposta.json["quantidade_templates"], 1)


if __name__ == "__main__":
    unittest.main()
