import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PASTA_MOTOR = Path(__file__).resolve().parents[1] / "automation_engine"
if str(PASTA_MOTOR) not in sys.path:
    sys.path.insert(0, str(PASTA_MOTOR))

import alertas_whatscontabil


class AlertasWhatsContabilTestCase(unittest.TestCase):
    def setUp(self):
        self.alerta = {
            "cnpj": "12345678000199",
            "empresa": "EMPRESA TESTE",
            "arquivo": "empresa.pfx",
            "vencimento": "2026-09-15",
            "dias": 15,
            "email": "cliente@example.com",
            "tipo_aviso": "aviso_15",
            "dados_cliente": {"telefone": "85999999999"},
        }

    @patch.object(alertas_whatscontabil, "sleep")
    @patch.object(alertas_whatscontabil, "registrar_alerta_enviado")
    @patch.object(alertas_whatscontabil, "enviar_mensagem_texto")
    @patch.object(alertas_whatscontabil, "enviar_template", return_value={
        "resposta": {"message": "Mensagem enviada com sucesso!"}
    })
    @patch.object(alertas_whatscontabil, "alerta_ja_enviado", return_value=True)
    def test_agendamento_de_teste_ignora_duplicidade(
        self,
        _duplicado,
        enviar_template_oficial,
        enviar_texto,
        _registrar,
        _sleep,
    ):
        with patch.dict(
            os.environ,
            {
                "MODO_WHATSCONTABIL": "teste",
                "WHATSCONTABIL_NUMERO_TESTE": "558596490370",
                "WHATSCONTABIL_TEMPLATE_TESTE": "alerta_certificado_teste",
            },
            clear=False,
        ):
            resumo = alertas_whatscontabil.enviar_alertas_internos(
                [self.alerta],
                PASTA_MOTOR,
                "5585999999999",
                2,
            )

        enviar_template_oficial.assert_called_once()
        self.assertEqual(
            enviar_template_oficial.call_args.args[1],
            "558596490370",
        )
        enviar_texto.assert_not_called()
        self.assertEqual(resumo["enviados"], 1)
        self.assertEqual(resumo["duplicados"], 0)

    @patch.object(alertas_whatscontabil, "enviar_mensagem_texto")
    @patch.object(alertas_whatscontabil, "alerta_ja_enviado", return_value=True)
    def test_fora_do_modo_teste_bloqueia_envio(self, _duplicado, enviar):
        with patch.dict(
            os.environ,
            {
                "MODO_WHATSCONTABIL": "desativado",
                "WHATSCONTABIL_NUMERO_TESTE": "558596490370",
            },
            clear=False,
        ):
            with self.assertRaises(alertas_whatscontabil.ErroWhatsContabil):
                alertas_whatscontabil.enviar_alertas_internos(
                    [self.alerta],
                    PASTA_MOTOR,
                    "5585999999999",
                    2,
                )

        enviar.assert_not_called()

    @patch.object(alertas_whatscontabil, "enviar_mensagem_texto")
    @patch.object(alertas_whatscontabil, "enviar_template")
    def test_sem_template_aprovado_nao_usa_texto_livre(
        self,
        enviar_template_oficial,
        enviar_texto,
    ):
        with patch.dict(
            os.environ,
            {
                "MODO_WHATSCONTABIL": "teste",
                "WHATSCONTABIL_NUMERO_TESTE": "558596490370",
                "WHATSCONTABIL_TEMPLATE_TESTE": "",
            },
            clear=False,
        ):
            resumo = alertas_whatscontabil.enviar_alertas_internos(
                [self.alerta],
                PASTA_MOTOR,
                "5585999999999",
                2,
            )

        enviar_template_oficial.assert_not_called()
        enviar_texto.assert_not_called()
        self.assertEqual(resumo["falhas"], 1)


if __name__ == "__main__":
    unittest.main()
