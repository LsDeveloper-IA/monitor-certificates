"""Regressões do upload com DOM local e sem carregar configurações reais."""

import ast
import re
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from playwright.sync_api import sync_playwright


ARQUIVO_AUTOMACAO = Path(__file__).resolve().parents[1] / "automacao.py"
XPATH_OPCAO = (
    "/html/body/div[6]/div/div[2]/section[2]/"
    "div/div[3]/div[2]/div[1]/div[2]/input"
)


class CertificadoRejeitadoError(RuntimeError):
    pass


def carregar_funcoes(*nomes, **dependencias):
    """Executa só helpers escolhidos, sem imports de config/Drive/persistência."""
    arvore = ast.parse(ARQUIVO_AUTOMACAO.read_text(encoding="utf-8-sig"))
    funcoes = [
        no for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name in nomes
    ]
    encontrados = {no.name for no in funcoes}
    if encontrados != set(nomes):
        raise AssertionError(f"Helpers não encontrados: {set(nomes) - encontrados}")
    namespace = {
        "re": re,
        "time": time,
        "print": Mock(),
        "CertificadoRejeitadoError": CertificadoRejeitadoError,
        **dependencias,
    }
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), str(ARQUIVO_AUTOMACAO), "exec"), namespace)
    return namespace


def modal_opcao(identificador, *, oculto=False, checked=False, disabled=False):
    atributos = f'id="{identificador}" type="checkbox"'
    if checked:
        atributos += " checked"
    if disabled:
        atributos += " disabled"
    campo = f"<div><div></div><div><input {atributos}></div></div>"
    conteudo = f"<div><div></div><div></div><div><div></div><div>{campo}</div></div></div>"
    estilo = ' style="display:none"' if oculto else ""
    return (
        f'<div role="dialog"{estilo}><div><div></div><div>'
        f"<section></section><section>{conteudo}</section></div></div></div>"
    )


class OpcaoDepoisUploadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        contexto = self.browser.new_context()
        self.addCleanup(contexto.close)
        self.page = contexto.new_page()
        self.rejeicao = Mock(return_value=None)
        self.garantir = carregar_funcoes(
            "garantir_input_ativo", obter_rejeicao_certificado=self.rejeicao,
        )["garantir_input_ativo"]

    def executar(self, **kwargs):
        self.garantir(self.page, XPATH_OPCAO, "opção de teste", timeout_ms=400, **kwargs)

    def test_modal_muda_da_sexta_para_setima_div(self):
        self.page.set_content("<div></div>" * 6 + modal_opcao("atual"))
        self.executar()
        self.assertTrue(self.page.locator("#atual").is_checked())

    def test_ignora_copia_oculta_da_etapa_no_modal_anterior(self):
        self.page.set_content(
            "<div></div>" * 5
            + modal_opcao("antigo", oculto=True)
            + modal_opcao("atual")
        )
        self.executar()
        self.assertFalse(self.page.locator("#antigo").is_checked())
        self.assertTrue(self.page.locator("#atual").is_checked())

    def test_nao_altera_nenhum_campo_se_dois_modais_correspondem(self):
        self.page.set_content(modal_opcao("primeiro") + modal_opcao("segundo"))
        with self.assertRaises(TimeoutError):
            self.executar()
        self.assertFalse(self.page.locator("#primeiro").is_checked())
        self.assertFalse(self.page.locator("#segundo").is_checked())

    def test_opcao_ja_marcada_e_desabilitada_nao_bloqueia_continuacao(self):
        self.page.set_content(modal_opcao("atual", checked=True, disabled=True))
        self.executar()
        self.assertTrue(self.page.locator("#atual").is_checked())
        self.assertTrue(self.page.locator("#atual").is_disabled())

    def test_opcao_desmarcada_e_desabilitada_nao_vira_sucesso(self):
        self.page.set_content(modal_opcao("atual", disabled=True))
        with self.assertRaises(TimeoutError):
            self.executar()
        self.assertFalse(self.page.locator("#atual").is_checked())

    def test_erro_explicito_do_certificado_interrompe_antes_de_marcar(self):
        self.page.set_content(modal_opcao("atual"))
        self.rejeicao.return_value = "Certificado incompatível com o CNPJ informado"
        with self.assertRaises(CertificadoRejeitadoError):
            self.executar(verificar_rejeicao=True)
        self.assertFalse(self.page.locator("#atual").is_checked())

    def test_ausencia_de_opcao_sem_rejeicao_e_falha_de_interface(self):
        self.page.set_content("<div role='dialog'>Salvar e continuar</div>")
        with self.assertRaises(TimeoutError) as erro:
            self.executar(verificar_rejeicao=True)
        self.assertNotIsInstance(erro.exception, CertificadoRejeitadoError)
        self.rejeicao.assert_called()

    def test_xpath_alternativo_mesmo_campo_nao_cria_ambiguidade(self):
        self.page.set_content(modal_opcao("atual"))
        self.executar(xpath_alternativo="//*[@id='atual']")
        self.assertTrue(self.page.locator("#atual").is_checked())


class EnvioCertificadoTest(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.candidato = {
            "arquivo_nome": "certificado-teste.pfx",
            "pfx_bytes": b"arquivo ficticio para mock",
            "senha": "senha-ficticia",
            "pasta_nome": "Pasta de teste",
        }
        self.preparar = Mock()
        self.validar = Mock(return_value=(True, "Senha correta"))
        self.avancar = Mock()
        self.marcar = Mock()
        self.enviar = carregar_funcoes(
            "enviar_certificado_candidato",
            preparar_tela_upload_certificado=self.preparar,
            aguardar_validacao_senha_certificado=self.validar,
            clicar_salvar_e_continuar=self.avancar,
            garantir_input_ativo=self.marcar,
            obter_rejeicao_certificado=Mock(return_value=None),
        )["enviar_certificado_candidato"]

    def executar(self):
        return self.enviar(self.page, self.candidato, "00000000000000", "Empresa de teste")

    def test_upload_aceito_avanca_e_verifica_as_duas_opcoes(self):
        self.executar()
        self.preparar.assert_called_once_with(self.page, "00000000000000", "Empresa de teste")
        campo = self.page.locator.return_value.last
        campo.set_input_files.assert_called_once_with({
            "name": self.candidato["arquivo_nome"],
            "mimeType": "application/x-pkcs12",
            "buffer": self.candidato["pfx_bytes"],
        })
        campo.fill.assert_called_once_with(self.candidato["senha"])
        self.validar.assert_called_once_with(self.page)
        self.avancar.assert_called_once_with(self.page, "certificado")
        self.assertEqual(self.marcar.call_count, 2)
        for chamada in self.marcar.call_args_list:
            self.assertTrue(chamada.kwargs["verificar_rejeicao"])

    def test_rejeicao_explicita_da_validacao_permite_trocar_candidato(self):
        self.validar.return_value = False, "Senha incorreta"
        with self.assertRaises(CertificadoRejeitadoError):
            self.executar()
        self.avancar.assert_not_called()
        self.marcar.assert_not_called()

    def test_validacao_inconclusiva_nao_acusa_rejeicao(self):
        self.validar.return_value = None, "Nenhuma resposta de validação"
        with self.assertRaises(RuntimeError) as erro:
            self.executar()
        self.assertNotIsInstance(erro.exception, CertificadoRejeitadoError)
        self.avancar.assert_not_called()

    def test_timeout_no_checkbox_apos_upload_nao_acusa_rejeicao(self):
        self.marcar.side_effect = TimeoutError("Opção não apareceu")
        with self.assertRaises(RuntimeError) as erro:
            self.executar()
        self.assertNotIsInstance(erro.exception, CertificadoRejeitadoError)
        self.assertEqual(self.marcar.call_count, 1)

    def test_timeout_no_botao_de_avanco_nao_acusa_rejeicao(self):
        self.avancar.side_effect = TimeoutError("Botão não apareceu")
        with self.assertRaises(RuntimeError) as erro:
            self.executar()
        self.assertNotIsInstance(erro.exception, CertificadoRejeitadoError)
        self.marcar.assert_not_called()

    def test_rejeicao_explicita_apos_upload_preserva_tipo_da_falha(self):
        self.marcar.side_effect = CertificadoRejeitadoError("Titular incompatível")
        with self.assertRaises(CertificadoRejeitadoError):
            self.executar()


class TentativasCandidatosTest(unittest.TestCase):
    def setUp(self):
        arvore = ast.parse(ARQUIVO_AUTOMACAO.read_text(encoding="utf-8-sig"))
        laços = [
            no for no in ast.walk(arvore)
            if isinstance(no, ast.For)
            and isinstance(no.target, ast.Name)
            and no.target.id == "candidato"
        ]
        self.assertEqual(len(laços), 1)
        self.codigo = compile(
            ast.Module(body=laços, type_ignores=[]), str(ARQUIVO_AUTOMACAO), "exec",
        )
        self.enviar = Mock()
        self.voltar = Mock(return_value=True)
        self.candidatos = [
            {"pasta_nome": f"Pasta {i}", "arquivo_nome": f"teste-{i}.pfx", "similaridade": 1.0}
            for i in (1, 2)
        ]
        self.namespace = {
            "print": Mock(),
            "candidatos": iter(self.candidatos),
            "total_tentativas": 0,
            "certificado_aceito": None,
            "rejeicoes": [],
            "page": Mock(),
            "cnpj": "00000000000000",
            "nome_empresa": "Empresa de teste",
            "enviar_certificado_candidato": self.enviar,
            "voltar_para_tabela_empresas": self.voltar,
            "CertificadoRejeitadoError": CertificadoRejeitadoError,
        }

    def test_falha_de_navegacao_nao_envia_segundo_certificado(self):
        self.enviar.side_effect = RuntimeError("Falha de navegação após upload")
        with self.assertRaises(RuntimeError):
            exec(self.codigo, self.namespace)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.namespace["rejeicoes"], [])
        self.voltar.assert_not_called()

    def test_rejeicao_explicita_tenta_proximo_certificado(self):
        self.enviar.side_effect = [CertificadoRejeitadoError("Senha incorreta"), None]
        exec(self.codigo, self.namespace)
        self.assertEqual(self.enviar.call_count, 2)
        self.assertEqual(self.namespace["certificado_aceito"], self.candidatos[1])
        self.assertEqual(len(self.namespace["rejeicoes"]), 1)
        self.voltar.assert_called_once()

    def test_rejeicao_sem_retorno_seguro_nao_tenta_outro_certificado(self):
        self.enviar.side_effect = CertificadoRejeitadoError("Senha incorreta")
        self.voltar.return_value = False
        with self.assertRaises(RuntimeError):
            exec(self.codigo, self.namespace)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertIsNone(self.namespace["certificado_aceito"])


    def test_candidato_aceito_encerra_tentativas(self):
        exec(self.codigo, self.namespace)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.namespace["rejeicoes"], [])
        self.assertIs(self.namespace["certificado_aceito"], self.candidatos[0])
        self.voltar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
