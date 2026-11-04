"""Regressões para selecionar a opção visível da paginação."""

import ast
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


ARQUIVO_SERVICE = Path(__file__).resolve().parents[1] / "sieg_service.py"


def carregar_seletor_paginacao():
    arvore = ast.parse(ARQUIVO_SERVICE.read_text(encoding="utf-8-sig"))
    funcao = next(
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef)
        and no.name == "_clicar_primeiro_visivel"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[funcao], type_ignores=[]), str(ARQUIVO_SERVICE), "exec"),
        namespace,
    )
    return namespace["_clicar_primeiro_visivel"]


class SeletorPaginacaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.contexto = self.browser.new_context()
        self.addCleanup(self.contexto.close)
        self.page = self.contexto.new_page()
        self.clicar = carregar_seletor_paginacao()

    def test_tenta_seletor_alternativo_se_o_xpath_so_encontrar_copia_oculta(self):
        self.page.set_content(
            '<div id="xpath" style="display:none">200</div>'
            '<ul role="listbox"><li role="option" '
            'onclick="this.dataset.clicked = \'yes\'">200</li></ul>'
        )
        clicou = self.clicar(
            self.page.locator("#xpath"),
            self.page.get_by_role("option", name="200", exact=True),
        )
        self.assertTrue(clicou)
        self.assertEqual(
            self.page.get_by_role("option", name="200").get_attribute("data-clicked"),
            "yes",
        )

    def test_nao_considera_suficiente_encontrar_apenas_opcao_oculta(self):
        self.page.set_content(
            '<li style="display:none" id="oculta">200</li>'
            '<li id="visivel">200</li>'
        )
        clicou = self.clicar(
            self.page.locator("#oculta"),
            self.page.locator("#visivel"),
        )
        self.assertTrue(clicou)

    def test_retorna_falso_quando_nao_existe_candidato_visivel_habilitado(self):
        self.page.set_content('<button disabled>200</button>')
        self.assertFalse(self.clicar(self.page.get_by_text("200", exact=True)))


if __name__ == "__main__":
    unittest.main()
