import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation_engine import registro_alertas


class RegistroAlertasTestCase(unittest.TestCase):
    def test_lista_sucesso_falha_e_destinatario_mascarado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "alertas.sqlite3"
            alerta = {
                "cnpj": "12345678000199",
                "arquivo": "certificado.pfx",
                "dias": 15,
                "vencimento": "2026-09-19",
                "email": "whatsapp:cliente_teste:558596490370",
            }
            with patch.object(registro_alertas, "CAMINHO_REGISTRO", caminho):
                registro_alertas.registrar_alerta_enviado(alerta)
                registro_alertas.registrar_evento_envio(
                    alerta,
                    "cliente",
                    "falhou",
                    "API indisponivel",
                )
                historico = registro_alertas.listar_alertas_enviados()

        self.assertEqual({item["status"] for item in historico}, {"enviado", "falhou"})
        self.assertTrue(all(item["destinatario"] == "***0370" for item in historico))
        self.assertIn("API indisponivel", {item["motivo"] for item in historico})


if __name__ == "__main__":
    unittest.main()
