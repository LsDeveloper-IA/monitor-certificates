import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PASTA_MOTOR = Path(__file__).resolve().parents[1] / "automation_engine"
if str(PASTA_MOTOR) not in sys.path:
    sys.path.insert(0, str(PASTA_MOTOR))

from integracoes.whatscontabil import (
    ErroWhatsContabil,
    _interpretar_erro_http,
    enviar_midia,
    enviar_template,
)


class WhatsContabilClientTestCase(unittest.TestCase):
    def test_erro_http_exibe_detalhe_aninhado_da_api(self):
        resposta = Mock(status_code=400)
        resposta.json.return_value = {
            "error": {"message": "Template temporariamente indisponivel"}
        }

        with self.assertRaises(ErroWhatsContabil) as contexto:
            _interpretar_erro_http(resposta)

        self.assertIn(
            "Template temporariamente indisponivel",
            str(contexto.exception),
        )

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

    @patch("integracoes.whatscontabil.requests.post")
    @patch(
        "integracoes.whatscontabil.carregar_configuracao",
        return_value=("https://whatscontabil.example", "token-seguro"),
    )
    def test_template_pode_anexar_planilha_excel(self, _configuracao, post):
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"messageIds": ["mensagem-1"]}
        post.return_value = resposta

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "relatorio.xlsx"
            caminho.write_bytes(b"arquivo-de-teste")

            resultado = enviar_template(
                PASTA_MOTOR,
                "5585999999999",
                "relatorio_teste",
                2,
                ["Equipe", "1"],
                arquivo=caminho,
            )

        nome, arquivo_enviado, tipo_mime = post.call_args.kwargs["files"]["files"]
        self.assertEqual(nome, "relatorio.xlsx")
        self.assertEqual(tipo_mime, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(arquivo_enviado.closed)
        self.assertEqual(resultado["status_http"], 200)

    @patch("integracoes.whatscontabil.requests.post")
    @patch(
        "integracoes.whatscontabil.carregar_configuracao",
        return_value=("https://whatscontabil.example", "token-seguro"),
    )
    def test_template_identifica_anexo_pdf(self, _configuracao, post):
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"messageIds": ["mensagem-1"]}
        post.return_value = resposta

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "relatorio.pdf"
            caminho.write_bytes(b"%PDF-arquivo-de-teste")

            enviar_template(
                PASTA_MOTOR,
                "5585999999999",
                "relatorio_teste",
                2,
                ["Equipe", "1"],
                arquivo=caminho,
            )

        nome, arquivo_enviado, tipo_mime = post.call_args.kwargs["files"]["files"]
        dados_enviados = post.call_args.kwargs["data"]
        self.assertEqual(nome, "relatorio.pdf")
        self.assertEqual(tipo_mime, "application/pdf")
        self.assertTrue(arquivo_enviado.closed)
        self.assertEqual(dados_enviados["to"], "5585999999999")
        self.assertEqual(dados_enviados["template"], "relatorio_teste")
        self.assertEqual(dados_enviados["whatsappId"], "2")
        self.assertEqual(dados_enviados["message"], '["Equipe", "1"]')

    @patch("integracoes.whatscontabil.requests.post")
    @patch(
        "integracoes.whatscontabil.carregar_configuracao",
        return_value=("https://whatscontabil.example", "token-seguro"),
    )
    def test_midia_usa_campo_medias_da_api(self, _configuracao, post):
        resposta = Mock(status_code=200)
        resposta.json.return_value = {"messageIds": ["mensagem-1"]}
        post.return_value = resposta

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "relatorio.pdf"
            caminho.write_bytes(b"%PDF-arquivo-de-teste")

            resultado = enviar_midia(
                PASTA_MOTOR,
                "5585999999999",
                "Relatorio de teste.",
                2,
                caminho,
            )

        campos = post.call_args.kwargs["files"]
        self.assertEqual(campos["to"], (None, "5585999999999"))
        self.assertEqual(campos["message"], (None, "Relatorio de teste."))
        self.assertEqual(campos["whatsappId"], (None, "2"))
        nome, arquivo_enviado, tipo_mime = campos["medias"]
        self.assertEqual(nome, "relatorio.pdf")
        self.assertEqual(tipo_mime, "application/pdf")
        self.assertTrue(arquivo_enviado.closed)
        self.assertEqual(resultado["status_http"], 200)


if __name__ == "__main__":
    unittest.main()
