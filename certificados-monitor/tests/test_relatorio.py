import os
import unittest
from unittest.mock import patch

from flask import Flask

from src.routes.relatorio import relatorio_bp


class RelatorioDriveTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["GOOGLE_DRIVE_PASTA_RELATORIOS_ID"] = "pasta-teste"
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(relatorio_bp, url_prefix="/api")
        self.cliente = app.test_client()

    def tearDown(self):
        os.environ.pop("GOOGLE_DRIVE_PASTA_RELATORIOS_ID", None)

    @patch("src.routes.relatorio.ler_relatorio_json_mais_recente")
    @patch("src.routes.relatorio.conectar_google_drive")
    def test_retorna_relatorio_valido(self, conectar, ler):
        conectar.return_value = object()
        ler.return_value = {
            "titulo": "RESUMO DA AUTOMAÇÃO SIEG",
            "resumo": {"sucessos": 0, "ignorados": 0, "falhas": 1},
            "empresas_com_falha": [
                {"cnpj": "36111966000143", "nome": "Empresa", "motivo": "Erro"}
            ],
        }
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["resumo"]["falhas"], 1)
        ler.assert_called_once_with(conectar.return_value, "pasta-teste")

    @patch("src.routes.relatorio.conectar_google_drive")
    def test_informa_quando_json_nao_existe(self, conectar):
        conectar.side_effect = FileNotFoundError("Nenhum arquivo JSON foi encontrado.")
        resposta = self.cliente.get("/api/relatorios/certificados-vencidos")
        self.assertEqual(resposta.status_code, 404)


if __name__ == "__main__":
    unittest.main()
