import os
import unittest
from unittest.mock import patch

from flask import Flask, jsonify

from src.seguranca import (
    acesso_administrativo_permitido,
    acesso_escrita_certificados_permitido,
    acesso_historico_permitido,
)


class AcessoProxyLocalTestCase(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.get("/administrativo")
        def administrativo():
            return jsonify({"permitido": acesso_administrativo_permitido()})

        @app.get("/historico")
        def historico():
            return jsonify({"permitido": acesso_historico_permitido()})

        @app.get("/escrita")
        def escrita():
            return jsonify({"permitido": acesso_escrita_certificados_permitido()})

        self.cliente = app.test_client()

    def test_proxy_local_libera_automacao_sem_chave_configurada(self):
        ambiente = {
            "AUTOMACAO_EXECUTION_KEY": "",
            "AUTOMACAO_ADMIN_KEY": "",
        }
        with patch.dict(os.environ, ambiente, clear=False):
            resposta = self.cliente.get(
                "/administrativo",
                headers={"X-Local-Proxy": "local"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json["permitido"])

    def test_proxy_local_libera_historico(self):
        with patch.dict(
            os.environ,
            {"AUTOMACAO_EXECUTION_KEY": "", "AUTOMACAO_ADMIN_KEY": ""},
            clear=False,
        ):
            resposta = self.cliente.get(
                "/historico",
                headers={"X-Local-Proxy": "local"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json["permitido"])

    def test_proxy_local_nao_autoriza_requisicao_remota(self):
        with patch.dict(
            os.environ,
            {"AUTOMACAO_EXECUTION_KEY": "", "AUTOMACAO_ADMIN_KEY": ""},
            clear=False,
        ):
            resposta = self.cliente.get(
                "/administrativo",
                headers={"X-Local-Proxy": "local"},
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json["permitido"])

    def test_proxy_local_nao_autoriza_escrita_de_certificados(self):
        with patch.dict(
            os.environ,
            {
                "AUTOMACAO_EXECUTION_KEY": "",
                "AUTOMACAO_ADMIN_KEY": "",
                "INTEGRACAO_API_KEY": "",
            },
            clear=False,
        ):
            resposta = self.cliente.get(
                "/escrita",
                headers={"X-Local-Proxy": "local"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json["permitido"])

    def test_chave_interna_continua_valida(self):
        with patch.dict(
            os.environ,
            {
                "AUTOMACAO_EXECUTION_KEY": "chave-interna-teste",
                "AUTOMACAO_ADMIN_KEY": "",
            },
            clear=False,
        ):
            resposta = self.cliente.get(
                "/administrativo",
                headers={"X-Automation-Key": "chave-interna-teste"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json["permitido"])


if __name__ == "__main__":
    unittest.main()
