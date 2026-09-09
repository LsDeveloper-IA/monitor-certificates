import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from docx import Document
from playwright.sync_api import sync_playwright
from sieg_comum import drive, navegacao, sessao


class NavegacaoTest(unittest.TestCase):
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

    def test_login_aguarda_formulario_e_confirma_sessao(self):
        self.page.set_content('''<input name="email"><input type="password">
            <button onclick="document.body.innerHTML='Todos os serviços'">Login</button>''')
        self.assertTrue(sessao.realizar_login_sieg(self.page, "teste@example.invalid", "teste"))
        self.assertTrue(sessao.realizar_login_sieg(self.page, "", ""))

    def test_clique_texto_css_e_xpath_ignora_elementos_ocultos(self):
        self.page.set_content('''<button style="display:none">Salvar</button>
            <button id="salvar" onclick="this.dataset.clicado='sim'">Salvar</button>''')
        for seletor in ("Salvar", "button#salvar", "//*[@id='salvar']"):
            self.assertTrue(navegacao.clicar_com_rolagem(self.page, seletor, tentativas=1))
            self.assertEqual(self.page.locator("#salvar").get_attribute("data-clicado"), "sim")

    def test_edicao_abre_por_clique_duplo(self):
        self.page.set_content('''<table><tr ondblclick="document.querySelector('h1').hidden=false"><td>Empresa</td></tr></table>
            <h1 hidden>Editar CNPJ/CPF</h1>''')
        self.assertTrue(navegacao.abrir_edicao_empresa(self.page, self.page.locator("tr")))

    def test_edicao_recupera_pelo_menu_quando_clique_duplo_falha(self):
        self.page.set_content('''<table><tr><td>Empresa</td><td><button
            onclick="document.querySelector('li').hidden=false">Opções</button></td></tr></table>
            <li hidden onclick="document.querySelector('h1').hidden=false">Editar cadastro</li>
            <h1 hidden>Editar CNPJ/CPF</h1>''')
        linha = Mock(wraps=self.page.locator("tr"))
        linha.dblclick.side_effect = RuntimeError("Clique duplo indisponível")
        self.assertTrue(navegacao.abrir_edicao_empresa(self.page, linha))

    def test_uf_nativa_preenche_vazio_e_preserva_estado_existente(self):
        for valor in ("", "SP"):
            self.page.set_content('''<label for="uf">UF</label><select id="uf">
                <option value="">Selecione</option><option value="CE">CE</option><option value="SP">SP</option></select>''')
            self.page.locator("select").select_option(valor)
            self.assertTrue(navegacao.preencher_uf(self.page, "CE"))
            self.assertEqual(self.page.locator("select").input_value(), valor or "CE")

    def test_uf_componente_customizado(self):
        self.page.set_content('''<label>Estado: <div><div><div onclick="document.querySelector('button').hidden=false">UF</div></div></div></label>
            <button hidden role="option" onclick="document.querySelector('label div div div').textContent='SP';this.hidden=true">SP</button>''')
        self.assertTrue(navegacao.preencher_uf(self.page, "SP"))
        self.assertIn("SP", self.page.locator("label").inner_text())

    def test_uf_rejeita_sigla_invalida(self):
        with self.assertRaisesRegex(ValueError, "UF inválida"):
            navegacao.preencher_uf_se_necessario(self.page, "XX")


class DriveTest(unittest.TestCase):
    def test_listagem_percorre_todas_paginas(self):
        service = Mock()
        service.files.return_value.list.return_value.execute.side_effect = [
            {"files": [{"id": "1", "name": "A"}], "nextPageToken": "proxima"},
            {"files": [{"id": "2", "name": "B"}]},
        ]
        self.assertEqual(len(drive.listar_pastas_no_drive(service, "raiz")), 2)
        self.assertEqual(service.files.return_value.list.call_args.kwargs["pageToken"], "proxima")

    def test_leitura_txt_docx_e_google_docs_normaliza_senha(self):
        arquivo = io.BytesIO()
        doc = Document()
        doc.add_paragraph("Senha: segredo")
        doc.save(arquivo)
        for nome, conteudo in (("senha.txt", io.BytesIO(b'\xef\xbb\xbfSenha: segredo\n')),
                               ("senha.docx", io.BytesIO(arquivo.getvalue()))):
            with patch.object(drive, "baixar_arquivo_drive", return_value=conteudo):
                self.assertEqual(drive.ler_senha_drive(Mock(), {"id": "1", "name": nome}), "segredo")
        with patch.object(drive, "exportar_google_doc", return_value="\u200bSenha: segredo"):
            self.assertEqual(drive.ler_senha_drive(Mock(), {"id": "1", "name": "senha", "mimeType": drive.MIME_GOOGLE_DOC}), "segredo")

    def test_politicas_busca_preservam_exato_e_contido(self):
        indice = {"por_nome": [("EMPRESA ALFA", {"id": "1"}),
                                ("EMPRESA ALFA FILIAL", {"id": "2"}), ("OUTRA", {"id": "3"})]}
        exato = drive._ordenar_pastas_por_similaridade("Empresa Alfa", indice, .85)
        contido = drive._ordenar_pastas_por_similaridade("Empresa Alfa", indice, 1, modo="contido")
        self.assertEqual(exato[0]["pasta"]["id"], "1")
        self.assertEqual([item["pasta"]["id"] for item in contido], ["1", "2"])
        self.assertEqual(drive._ordenar_pastas_por_similaridade("", indice, 1, modo="contido"), [])

    def test_token_json_valido_nao_abre_autorizacao(self):
        creds = SimpleNamespace(valid=True, has_scopes=bool)
        with tempfile.TemporaryDirectory() as pasta, patch.object(drive, "build") as build, \
                patch.object(drive, "InstalledAppFlow") as flow:
            token_json = Path(pasta) / "token.json"
            token_json.write_text("{}", encoding="utf-8")
            with patch.object(drive.Credentials, "from_authorized_user_file", return_value=creds):
                drive.autenticar_drive(Path(pasta) / "credentials.json", token_json, ["drive"])
            self.assertEqual(build.call_count, 1)
            flow.from_client_secrets_file.assert_not_called()

    def test_recusa_token_pickle_antes_de_ler_o_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            token = Path(pasta) / "token.pickle"
            token.write_bytes(b"conteudo que nao deve ser desserializado")
            with self.assertRaisesRegex(ValueError, "token.json"):
                drive.autenticar_drive(Path(pasta) / "credentials.json", token, ["drive"])

    def test_refresh_invalido_reautoriza_e_grava_token_json(self):
        with tempfile.TemporaryDirectory() as pasta:
            token = Path(pasta) / "token.json"
            token.write_text("{}", encoding="utf-8")
            credentials = Path(pasta) / "credentials.json"
            credentials.write_text("{}", encoding="utf-8")
            antigo = Mock(valid=False, expired=True, refresh_token="token")
            antigo.refresh.side_effect = drive.RefreshError("revogado")
            novo = Mock(valid=True)
            novo.to_json.return_value = '{"novo": true}'
            with patch.object(drive.Credentials, "from_authorized_user_file", return_value=antigo), \
                    patch.object(drive, "InstalledAppFlow") as flow, patch.object(drive, "build"):
                flow.from_client_secrets_file.return_value.run_local_server.return_value = novo
                drive.autenticar_drive(credentials, token, ["drive"])
                self.assertEqual(token.read_text(encoding="utf-8"), '{"novo": true}')
                flow.from_client_secrets_file.return_value.run_local_server.assert_called_once_with(port=0)

    def test_varias_senhas_e_certificados_continuam_sendo_validados(self):
        arquivos = [{"id": "a", "name": "cert.pfx"}, {"id": "b", "name": "senha.txt"},
                    {"id": "c", "name": "outra.txt"}]
        with patch.object(drive, "listar_itens_drive", return_value=arquivos), \
                patch.object(drive, "ler_senha_drive", side_effect=["errada", "correta"]), \
                patch.object(drive, "baixar_arquivo_drive", return_value=io.BytesIO(b'pfx')), \
                patch.object(drive, "verificar_validade_certificado_bytes", side_effect=[False, True]):
            resultado = drive._extrair_certificados_da_pasta_drive("pasta", Mock())
            self.assertEqual(resultado[0]["senha"], "correta")

    def test_auto_nc_continua_na_pasta_seguinte_e_retorna_caminho(self):
        indice = {"por_nome": [("EMPRESA ALFA", {"id": "1", "name": "Empresa Alfa"}),
                                ("EMPRESA ALFA FILIAL", {"id": "2", "name": "Empresa Alfa Filial"})]}
        arquivos = [{"id": "a", "name": "cert.pfx"}, {"id": "b", "name": "senha.docx"}]
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(drive, "criar_indice_pastas_drive", return_value=indice), \
                patch.object(drive, "listar_itens_drive", return_value=arquivos), \
                patch.object(drive, "baixar_arquivo_drive", side_effect=lambda *args: io.BytesIO(b'pfx')), \
                patch.object(drive, "ler_senha_drive", side_effect=[ValueError("Documento ilegível"), "senha"]):
            caminho, senha = drive.buscar_arquivos_por_nome_empresa("Empresa Alfa", Mock(), "raiz", pasta)
            self.assertEqual(Path(caminho).read_bytes(), b'pfx')
            self.assertEqual(senha, "senha")


if __name__ == "__main__":
    unittest.main()
