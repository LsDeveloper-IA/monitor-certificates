import unittest

from playwright.sync_api import sync_playwright
from sieg_comum.modais import botao_modal, botao_atualizar_certificado, campo_upload_modal


class ModaisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def test_botao_so_no_ultimo_modal_visivel(self):
        self.page.set_content('''<button>Salvar e continuar</button>
            <div role="dialog"><button id="antigo">Salvar e continuar</button></div>
            <aside><div role="dialog"><main><footer><button id="atual"
                onclick="this.dataset.clicado='sim'">Salvar e continuar</button></footer></main></div></aside>
            <div role="dialog" style="display:none"><button>Salvar e continuar</button></div>''')
        botao_modal(self.page, "Salvar e continuar").click()
        self.assertEqual(self.page.locator("#atual").get_attribute("data-clicado"), "sim")
        self.assertIsNone(self.page.locator("#antigo").get_attribute("data-clicado"))

    def test_upload_oculto_e_senha_pertencem_ao_modal_ativo(self):
        self.page.set_content('''<input type="file"><input type="password">
            <div role="dialog"><input type="password" id="antigo"></div>
            <div role="dialog"><label>Certificado<input type="file" hidden id="arquivo"></label>
                <label>Senha<input type="password" id="senha"></label></div>''')
        self.assertEqual(campo_upload_modal(self.page, "file").get_attribute("id"), "arquivo")
        campo_upload_modal(self.page, "password").fill("teste")
        self.assertEqual(self.page.locator("#senha").input_value(), "teste")
        self.assertEqual(self.page.locator("#antigo").input_value(), "")

    def test_atualizacao_identificada_por_nome_ou_tooltip(self):
        for atributo in ('aria-label="Atualizar certificado"', 'title="Atualizar certificado"',
                         'data-tooltip="Atualizar certificado"'):
            self.page.set_content(f'''<button aria-label="Atualizar certificado">Fora</button>
                <div role="dialog"><button aria-label="Fechar">X</button><section><article>
                    <button {atributo} id="atualizar"></button></article></section></div>''')
            self.assertEqual(botao_atualizar_certificado(self.page).get_attribute("id"), "atualizar")

    def test_icone_generico_nao_e_confundido_com_atualizacao(self):
        self.page.set_content('''<div role="dialog"><span>Vencido</span>
            <button><svg></svg></button><button>Salvar e continuar</button></div>''')
        self.assertEqual(botao_atualizar_certificado(self.page).count(), 0)

    def test_botao_duplicado_no_modal_nao_escolhe_por_posicao(self):
        self.page.set_content('''<div role="dialog"><button>Atualizar certificado</button>
            <button>Atualizar certificado</button></div>''')
        self.assertEqual(botao_atualizar_certificado(self.page).count(), 2)
        with self.assertRaises(Exception):
            botao_atualizar_certificado(self.page).click(timeout=200)


if __name__ == "__main__":
    unittest.main()
