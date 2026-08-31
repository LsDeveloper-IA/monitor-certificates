import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


PASTA_MOTOR = Path(__file__).resolve().parents[1] / "automation_engine"
if str(PASTA_MOTOR) not in sys.path:
    sys.path.insert(0, str(PASTA_MOTOR))

from integracoes.whatscontabil import ErroWhatsContabil, _interpretar_erro_http


class WhatsContabilClientTestCase(unittest.TestCase):
    def test_erro_http_inclui_detalhe_seguro_da_api(self):
        resposta = Mock(status_code=400)
        resposta.json.return_value = {
            "message": "Variavel 2 invalida para o template"
        }

        with self.assertRaises(ErroWhatsContabil) as contexto:
            _interpretar_erro_http(resposta)

        mensagem = str(contexto.exception)
        self.assertIn("api", mensagem.casefold())
        self.assertIn("Variavel 2 invalida", mensagem)

    def test_erro_http_ignora_campos_sensiveis(self):
        resposta = Mock(status_code=401)
        resposta.json.return_value = {
            "token": "segredo-que-nao-pode-aparecer",
            "authorization": "Bearer segredo",
        }

        with self.assertRaises(ErroWhatsContabil) as contexto:
            _interpretar_erro_http(resposta)

        mensagem = str(contexto.exception)
        self.assertNotIn("segredo", mensagem)


if __name__ == "__main__":
    unittest.main()
