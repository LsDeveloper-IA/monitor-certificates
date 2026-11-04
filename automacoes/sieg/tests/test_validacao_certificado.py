"""Valida mensagens reais no DOM local, sem carregar config ou acessar o SIEG."""

import ast
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright


def carregar_funcoes_validacao():
    caminho = Path(__file__).resolve().parents[1] / "sieg_service.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    nomes = {
        "CertificadoRejeitadoError",
        "_script_validacao_certificado",
        "obter_rejeicao_certificado",
        "aguardar_validacao_senha_certificado",
    }
    arvore.body = [
        no for no in arvore.body
        if isinstance(no, (ast.FunctionDef, ast.ClassDef)) and no.name in nomes
    ]
    namespace = {"print": lambda *args, **kwargs: None}
    exec(compile(arvore, str(caminho), "exec"), namespace)
    return namespace


FUNCOES = carregar_funcoes_validacao()


class ValidacaoCertificadoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def rejeicao(self):
        return FUNCOES["obter_rejeicao_certificado"](self.page)

    def validacao(self):
        return FUNCOES["aguardar_validacao_senha_certificado"](
            self.page, timeout_ms=150
        )

    def test_rejeicoes_explicitas_de_senha_certificado_e_empresa(self):
        mensagens = (
            "A senha está incorreta.",
            "Senha inválida.",
            "A senha não confere.",
            "Certificado digital inválido.",
            "O certificado enviado não pertence ao CNPJ informado.",
            "O CNPJ do certificado não corresponde ao CNPJ do cadastro.",
            "O titular do certificado é diferente da empresa.",
            "CPF incompatível com o certificado informado.",
        )
        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.page.set_content(f'<div role="alert">{mensagem}</div>')
                self.assertIsNotNone(self.rejeicao())
                estado, detalhe = self.validacao()
                self.assertIs(estado, False)
                self.assertTrue(detalhe)

    def test_erro_tem_prioridade_sobre_sucesso_anterior_no_dom(self):
        self.page.set_content('''
            <div role="alert">Senha validada com sucesso.</div>
            <div role="dialog">CNPJ do certificado incompatível.</div>
        ''')
        self.assertIn("CNPJ", self.rejeicao())
        self.assertIs(self.validacao()[0], False)

    def test_senha_validada_nao_e_rejeicao(self):
        self.page.set_content('<div class="toast">Senha validada com sucesso.</div>')
        self.assertIsNone(self.rejeicao())
        self.assertIs(self.validacao()[0], True)

    def test_mensagens_de_sucesso_suportadas(self):
        for mensagem in (
            "Senha correta", "Senha válida", "Certificado carregado",
            "Certificado atualizado com sucesso", "Sucesso ao importar certificado",
        ):
            with self.subTest(mensagem=mensagem):
                self.page.set_content(f'<div class="notification">{mensagem}</div>')
                self.assertIs(self.validacao()[0], True)
                self.assertIsNone(self.rejeicao())

    def test_rejeicoes_ocultas_nao_invalidam_sucesso_visivel(self):
        self.page.set_content('''
            <div role="alert" style="display:none">Senha incorreta</div>
            <div role="dialog" style="visibility:hidden">Certificado inválido</div>
            <div role="alert">Senha correta</div>
        ''')
        self.assertIsNone(self.rejeicao())
        self.assertIs(self.validacao()[0], True)

    def test_vencimento_erros_de_interface_e_ausencia_sao_inconclusivos(self):
        for mensagem in (
            "Certificado Vencido", "Certificado Vencida", "Certificado expirado",
            "Erro ao carregar o certificado", "Falha de rede durante upload",
            "Senha não validada", "Aguardando validação", "",
        ):
            with self.subTest(mensagem=mensagem):
                self.page.set_content(f'<div role="dialog">{mensagem}</div>')
                self.assertIsNone(self.rejeicao())
                estado, detalhe = self.validacao()
                self.assertIsNone(estado)
                self.assertIn("inconclusiva", detalhe)

    def test_erro_fora_de_alerta_ou_modal_nao_e_rejeicao(self):
        self.page.set_content('<p>Senha inválida</p>')
        self.assertIsNone(self.rejeicao())

    def test_erro_de_interface_nao_e_rejeicao(self):
        class PaginaIndisponivel:
            def wait_for_function(self, *args, **kwargs):
                raise RuntimeError("Página fechada")

        estado, detalhe = FUNCOES["aguardar_validacao_senha_certificado"](
            PaginaIndisponivel(), timeout_ms=150
        )
        self.assertIsNone(estado)
        self.assertIn("inconclusiva", detalhe)

    def test_classe_de_rejeicao_e_distinta_de_timeout(self):
        classe = FUNCOES["CertificadoRejeitadoError"]
        self.assertTrue(issubclass(classe, RuntimeError))
        self.assertEqual(str(classe("Senha incorreta")), "Senha incorreta")


if __name__ == "__main__":
    unittest.main()
