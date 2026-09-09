import ast
import sys
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
import unittest
from unittest.mock import Mock


class BaseEmpresasTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.base = Path(pasta.name) / "empresas_sieg.json"
        self.sem_certificado = Path(pasta.name) / "empresas_sem_certificado.json"
        caminho = Path(__file__).resolve().parents[1] / "main.py"
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        funcoes = {"normalizar_texto", "ler_empresas_sieg_da_pagina",
                   "salvar_base_empresas_sieg", "salvar_empresas_sem_certificado"}
        arvore.body = [no for no in arvore.body if isinstance(no, ast.FunctionDef) and no.name in funcoes]
        sys.path.insert(0, str(caminho.parents[1]))
        from sieg_comum.identidade import normalizar_texto
        self.namespace = {"normalizar_texto": normalizar_texto, "datetime": datetime, "json": json, "os": os, "re": re,
                          "unicodedata": unicodedata, "ARQUIVO_EMPRESAS_SIEG": self.base,
                          "ARQUIVO_RELATORIO_SEM_CERTIFICADO": self.sem_certificado}
        exec(compile(arvore, str(caminho), "exec"), self.namespace)

    def test_coleta_documento_da_empresa_e_estado_do_input(self):
        page = Mock()
        page.locator.return_value.first.locator.return_value.evaluate.return_value = [
            {"nome": "Empresa Exemplo\nCNPJ: 12.345.678/0001-90 • CE", "ativo_sieg": True},
            {"nome": "Pessoa Fisica\nCPF: 123.456.789-01 • CE", "ativo_sieg": False},
            {"nome": "Incompleta\nCNPJ: 12345 • -", "ativo_sieg": True},
        ]
        empresas = self.namespace["ler_empresas_sieg_da_pagina"](page)
        self.assertEqual(empresas, [
            {"nome": "Empresa Exemplo", "cnpj": "12345678000190", "ativo_sieg": True},
            {"nome": "Pessoa Fisica", "cnpj": "12345678901", "ativo_sieg": False},
            {"nome": "Incompleta", "cnpj": "", "ativo_sieg": True},
        ])

    def test_base_conta_apenas_cnpjs_ativos_unicos(self):
        empresas = [
            {"nome": "Matriz", "cnpj": "12.345.678/0001-90", "ativo_sieg": True},
            {"nome": "Outro nome da matriz", "cnpj": "12345678000190", "ativo_sieg": True},
            {"nome": "Filial", "cnpj": "12345678000270", "ativo_sieg": True},
            {"nome": "Inativa", "cnpj": "11111111000100", "ativo_sieg": False},
            {"nome": "Pessoa", "cnpj": "12345678901", "ativo_sieg": True},
            {"nome": "Incompleta", "cnpj": "12345", "ativo_sieg": True},
        ]
        self.assertTrue(self.namespace["salvar_base_empresas_sieg"](empresas, len(empresas)))
        dados = json.loads(self.base.read_text(encoding="utf-8"))
        self.assertTrue(dados["completo"])
        self.assertEqual({item["cnpj"] for item in dados["empresas"]},
                         {"12345678000190", "12345678000270"})

    def test_leitura_incompleta_ou_repetida_preserva_base_anterior(self):
        anterior = '{"completo": true, "empresas": []}'
        self.base.write_text(anterior, encoding="utf-8")
        empresa = {"nome": "Empresa", "cnpj": "12345678000190", "ativo_sieg": True}
        for empresas, total in (([empresa], 2), ([empresa, empresa], 2), ([empresa], None)):
            with self.subTest(empresas=len(empresas), total=total):
                self.assertFalse(self.namespace["salvar_base_empresas_sieg"](empresas, total))
                self.assertEqual(self.base.read_text(encoding="utf-8"), anterior)

    def test_sem_certificado_nao_preserva_maximo_historico_e_deduplica_documentos(self):
        self.sem_certificado.write_text('{"maior_quantidade": 999, "empresas": []}', encoding="utf-8")
        self.namespace["salvar_empresas_sem_certificado"]([
            {"nome": "Empresa", "cnpj": "12.345.678/0001-90"},
            {"nome": "Empresa", "cnpj": "12345678000190"},
            {"nome": "Empresa", "cnpj": "12345678000270"},
        ])
        dados = json.loads(self.sem_certificado.read_text(encoding="utf-8"))
        self.assertNotIn("maior_quantidade", dados)
        self.assertEqual(len(dados["empresas"]), 2)
        self.namespace["salvar_empresas_sem_certificado"]([])
        self.assertEqual(json.loads(self.sem_certificado.read_text(encoding="utf-8"))["empresas"], [])


if __name__ == "__main__":
    unittest.main()
