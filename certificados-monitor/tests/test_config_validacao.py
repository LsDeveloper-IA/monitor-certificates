"""Testes da validacao central de configuracao do painel.

O modulo e carregado pelo caminho porque ``automacoes/sieg`` tambem possui um
``config.py`` e, na execucao unica do pytest, ``import config`` resolve para ele.
"""

import importlib.util
from pathlib import Path
import sys
import unittest


RAIZ = Path(__file__).resolve().parents[2]
CAMINHO = RAIZ / "config" / "validacao.py"
SPEC = importlib.util.spec_from_file_location("monitor_config_validacao", CAMINHO)
VALIDACAO = importlib.util.module_from_spec(SPEC)
# dataclasses resolve anotacoes por sys.modules; registre antes de executar.
sys.modules[SPEC.name] = VALIDACAO
SPEC.loader.exec_module(VALIDACAO)


class ConfiguracaoTest(unittest.TestCase):
    def test_usa_padroes_quando_o_ambiente_esta_vazio(self):
        configuracao = VALIDACAO.carregar_configuracao({})

        self.assertFalse(configuracao.debug)
        self.assertEqual(configuracao.host, "127.0.0.1")
        self.assertEqual(configuracao.porta, 5000)
        self.assertEqual(configuracao.frontend_origem, "http://localhost:3000")
        self.assertEqual(configuracao.api_monitor_url, "http://localhost:5000")
        self.assertIsNone(configuracao.storage_dir)
        self.assertEqual(
            configuracao.secret_key, "altere-esta-chave-no-env"
        )

    def test_le_booleano_e_inteiro_validos(self):
        configuracao = VALIDACAO.carregar_configuracao(
            {
                "FLASK_DEBUG": "sim",
                "FLASK_PORT": "8080",
                "FLASK_HOST": "0.0.0.0",
                "FRONTEND_ORIGIN": "https://painel.exemplo.com/",
            }
        )

        self.assertTrue(configuracao.debug)
        self.assertEqual(configuracao.porta, 8080)
        self.assertEqual(configuracao.host, "0.0.0.0")
        self.assertEqual(
            configuracao.frontend_origem, "https://painel.exemplo.com"
        )

    def test_recusa_porta_invalida(self):
        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "FLASK_PORT"
        ):
            VALIDACAO.carregar_configuracao({"FLASK_PORT": "abc"})

        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "entre 1 e 65535"
        ):
            VALIDACAO.carregar_configuracao({"FLASK_PORT": "70000"})

    def test_recusa_booleano_invalido(self):
        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "FLASK_DEBUG"
        ):
            VALIDACAO.carregar_configuracao({"FLASK_DEBUG": "talvez"})

    def test_recusa_url_sem_esquema(self):
        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "FRONTEND_ORIGIN"
        ):
            VALIDACAO.carregar_configuracao(
                {"FRONTEND_ORIGIN": "painel.exemplo.com"}
            )

    def test_resolve_storage_relativo_a_partir_da_raiz(self):
        configuracao = VALIDACAO.carregar_configuracao(
            {"STORAGE_DIR": "dados"}
        )

        self.assertEqual(configuracao.storage_dir, (RAIZ / "dados").resolve())

    def test_preserva_storage_absoluto(self):
        destino = (RAIZ / "storage" / "outro").resolve()
        configuracao = VALIDACAO.carregar_configuracao(
            {"STORAGE_DIR": str(destino)}
        )

        self.assertEqual(configuracao.storage_dir, destino)

    def test_modo_estrito_exige_segredos_proprios(self):
        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "SECRET_KEY"
        ):
            VALIDACAO.carregar_configuracao(
                {"MONITOR_CONFIG_STRICT": "sim"}
            )

    def test_modo_estrito_aceita_segredos_definidos(self):
        configuracao = VALIDACAO.carregar_configuracao(
            {
                "MONITOR_CONFIG_STRICT": "sim",
                "SECRET_KEY": "chave-local",
                "INTEGRACAO_API_KEY": "integracao-local",
                "AUTOMACAO_EXECUTION_KEY": "execucao-local",
            }
        )

        self.assertEqual(configuracao.secret_key, "chave-local")
        self.assertEqual(configuracao.integracao_api_key, "integracao-local")
        self.assertEqual(
            configuracao.automacao_execution_key, "execucao-local"
        )

    def test_permite_forcar_validacao_por_parametro(self):
        with self.assertRaisesRegex(
            VALIDACAO.ErroConfiguracao, "SECRET_KEY"
        ):
            VALIDACAO.carregar_configuracao({}, exigir_segredos=True)

        configuracao = VALIDACAO.carregar_configuracao(
            {"MONITOR_CONFIG_STRICT": "talvez"},
            exigir_segredos=False,
        )
        self.assertEqual(configuracao.porta, 5000)


if __name__ == "__main__":
    unittest.main()
