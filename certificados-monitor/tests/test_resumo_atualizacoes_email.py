import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation_engine.resumo_atualizacoes_email import (
    enviar_resumo_atualizacoes,
    montar_resumo_atualizacoes,
)


ALTERACAO = {
    "tipo": "renovado",
    "empresa": "Empresa Teste",
    "cnpj": "12345678000190",
    "vencimento_anterior": "2026-09-10",
    "vencimento_novo": "2027-09-10",
}


class ResumoAtualizacoesEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.pasta_temporaria = tempfile.TemporaryDirectory()
        os.environ["HISTORICO_RESUMO_ATUALIZACOES"] = str(
            Path(self.pasta_temporaria.name) / "historico.json"
        )

    def tearDown(self):
        os.environ.pop("ENVIAR_RESUMO_ATUALIZACOES_AUTOMATICO", None)
        os.environ.pop("EMAIL_RESUMO_ATUALIZACOES", None)
        os.environ.pop("HISTORICO_RESUMO_ATUALIZACOES", None)
        self.pasta_temporaria.cleanup()

    def test_monta_um_resumo_legivel(self):
        assunto, texto, mensagem_html = montar_resumo_atualizacoes([ALTERACAO])

        self.assertIn("1 empresa(s)", assunto)
        self.assertIn("Empresa Teste (12.345.678/0001-90)", texto)
        self.assertIn("10/09/2026 → 10/09/2027", texto)
        self.assertIn("<li", mensagem_html)

    @patch("automation_engine.resumo_atualizacoes_email.enviar_email")
    def test_envia_um_unico_email_quando_habilitado(self, enviar):
        enviar.return_value = "message-id"
        os.environ["ENVIAR_RESUMO_ATUALIZACOES_AUTOMATICO"] = "sim"
        os.environ["EMAIL_RESUMO_ATUALIZACOES"] = "equipe@example.com"

        resultado = enviar_resumo_atualizacoes(
            {"alteracoes_certificados": [ALTERACAO]}
        )

        self.assertEqual(resultado["status"], "enviado")
        enviar.assert_called_once()

    @patch("automation_engine.resumo_atualizacoes_email.enviar_email")
    def test_nao_envia_quando_nao_ha_alteracoes(self, enviar):
        os.environ["ENVIAR_RESUMO_ATUALIZACOES_AUTOMATICO"] = "sim"
        os.environ["EMAIL_RESUMO_ATUALIZACOES"] = "equipe@example.com"

        resultado = enviar_resumo_atualizacoes({"alteracoes_certificados": []})

        self.assertEqual(resultado["status"], "sem_alteracoes")
        enviar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
