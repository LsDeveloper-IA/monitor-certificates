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

    def test_modal_sem_atributos_de_acessibilidade(self):
        for classe in ("su-modal", "modal", "drawer", "su-drawer"):
            with self.subTest(classe=classe):
                self.page.set_content(f'''<input type="password" id="fora">
                    <div role="dialog"><input type="password" id="antigo"></div>
                    <div class="{classe}">
                        <input type="file" hidden id="arquivo">
                        <input type="password" id="senha">
                        <footer class="modal-footer"><button
                            onclick="this.dataset.clicado='sim'" id="salvar"
                            >Salvar e continuar</button></footer>
                    </div>
                    <div class="modal-backdrop">Fundo</div>
                    <div class="{classe}" style="display:none">
                        <input type="password"></div>''')
                campo_upload_modal(self.page, "password", timeout=500).fill("teste")
                self.assertEqual(campo_upload_modal(self.page, "file").get_attribute("id"), "arquivo")
                botao_modal(self.page, "Salvar e continuar").click()
                self.assertEqual(self.page.locator("#salvar").get_attribute("data-clicado"), "sim")
                self.assertEqual(self.page.locator("#senha").input_value(), "teste")
                self.assertEqual(self.page.locator("#fora").input_value(), "")
                self.assertEqual(self.page.locator("#antigo").input_value(), "")

    def test_atualizacao_identificada_por_nome_ou_tooltip(self):
        for atributo in ('aria-label="Atualizar certificado"', 'title="Atualizar certificado"',
                         'data-tooltip="Atualizar certificado"'):
            self.page.set_content(f'''<button aria-label="Atualizar certificado">Fora</button>
                <div role="dialog"><button aria-label="Fechar">X</button><section><article>
                    <button {atributo} id="atualizar"></button></article></section></div>''')
            self.assertEqual(botao_atualizar_certificado(self.page).get_attribute("id"), "atualizar")

    def test_painel_posicionado_sem_role_ou_classe_modal(self):
        self.page.set_content('''<main style="position:absolute">
            <table><tr><td>Empresa</td></tr></table>
            <button>Salvar e continuar</button></main>
            <div style="position:fixed; right:0; top:0">
              <header>Editar CNPJ/CPF</header><section>
              <input type="password" id="senha"></section>
              <footer><button>Salvar e continuar</button></footer></div>''')
        campo_upload_modal(self.page, "password", timeout=500).fill("teste")
        self.assertEqual(self.page.locator("#senha").input_value(), "teste")
        self.assertEqual(botao_modal(self.page, "Salvar e continuar").count(), 1)

    def test_nao_trata_tabela_ou_botao_solto_como_modal(self):
        from sieg_comum.modais import modal_visivel
        self.page.set_content('''<main style="position:fixed">
            <table><tr><td>Empresa</td></tr></table>
            <div><button>Salvar e continuar</button></div></main>''')
        with self.assertRaises(TimeoutError):
            modal_visivel(self.page, timeout=200)

    def test_icone_generico_nao_e_confundido_com_atualizacao(self):
        self.page.set_content('''<div role="dialog"><span>Vencido</span>
            <button><svg></svg></button><button>Salvar e continuar</button></div>''')
        self.assertEqual(botao_atualizar_certificado(self.page).count(), 0)

    def test_botao_sem_rotulo_no_caminho_informado(self):
        def painel(identificador, estilo=""):
            return f'''<div style="position:fixed; {estilo}"><div>
                <div></div><div><section></section><section><section><div>
                <div></div><div><div><div></div><div><div><div>
                <button id="{identificador}" onclick="this.dataset.clicado='sim'">
                <svg width="20" height="20"></svg></button>
                </div></div></div></div></div></div></section></section>
                <button>Salvar e continuar</button></div></div></div>'''
        for quantidade in (5, 6):
            with self.subTest(divs_anteriores=quantidade):
                self.page.set_content(
                    "<div></div>" * quantidade + painel("atual")
                    + painel("oculto", "display:none")
                )
                botao = botao_atualizar_certificado(self.page)
                self.assertEqual(botao.get_attribute("id"), "atual")
                botao.click()
                self.assertEqual(self.page.locator("#atual").get_attribute("data-clicado"), "sim")
                self.assertIsNone(self.page.locator("#oculto").get_attribute("data-clicado"))

    def test_botao_duplicado_no_modal_nao_escolhe_por_posicao(self):
        self.page.set_content('''<div role="dialog"><button>Atualizar certificado</button>
            <button>Atualizar certificado</button></div>''')
        self.assertEqual(botao_atualizar_certificado(self.page).count(), 2)
        with self.assertRaises(Exception):
            botao_atualizar_certificado(self.page).click(timeout=200)


if __name__ == "__main__":
    unittest.main()
