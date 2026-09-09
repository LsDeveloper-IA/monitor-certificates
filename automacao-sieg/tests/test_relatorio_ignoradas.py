import ast
from datetime import datetime
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock


class RelatorioIgnoradasTest(unittest.TestCase):
    def setUp(self):
        caminho = Path(__file__).resolve().parents[1] / "persistencia.py"
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        arvore.body = [no for no in arvore.body if isinstance(no, ast.FunctionDef)
                       and no.name == "gerar_resumo_execucao"]
        self.servico = Mock()
        self.servico.files.return_value.create.return_value.execute.return_value = {"id": "novo"}
        self.servico.files.return_value.list.return_value.execute.return_value = {"files": []}
        namespace = {
            "io": io, "json": json,
            "_agora": lambda: datetime(2026, 9, 8, 12),
            "DRIVE_RELATORIOS_FOLDER_ID": "pasta-teste",
            "validar_pastas_drive": lambda: None,
            "MediaIoBaseUpload": lambda arquivo, **kwargs: json.load(arquivo),
        }
        exec(compile(arvore, str(caminho), "exec"), namespace)
        self.gerar = namespace["gerar_resumo_execucao"]

    def test_relatorio_identifica_empresas_ignoradas(self):
        empresas = [{"cnpj": "12345678000190", "nome": "Empresa Exemplo"}]
        self.gerar(0, [], 1, self.servico, empresas_ignoradas=empresas)
        dados = self.servico.files.return_value.create.call_args.kwargs["media_body"]
        self.assertEqual(dados["empresas_ignoradas"], empresas)
        self.assertEqual(dados["resumo"]["ignorados"], 1)

    def test_chamada_antiga_nao_inventa_identidades_para_ignorados(self):
        self.gerar(0, [], 10, self.servico)
        dados = self.servico.files.return_value.create.call_args.kwargs["media_body"]
        self.assertEqual(dados["empresas_ignoradas"], [])


if __name__ == "__main__":
    unittest.main()
