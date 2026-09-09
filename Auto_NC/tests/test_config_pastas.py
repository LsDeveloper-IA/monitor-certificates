import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


CAMINHO = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("auto_nc_config_teste", CAMINHO)
AUTO_NC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTO_NC)


class ConfigPastasTest(unittest.TestCase):
    def test_relatorio_falha_antes_de_consultar_drive_sem_pasta(self):
        servico = Mock()
        with patch.object(AUTO_NC, "ID_PASTA_DRIVE_RELATORIO", ""):
            with self.assertRaisesRegex(RuntimeError, "AUTO_NC_REPORT_FOLDER_ID"):
                AUTO_NC.enviar_relatorio_para_drive(servico)
        servico.files.assert_not_called()

    def test_execucao_informa_as_duas_variaveis_ausentes(self):
        with patch.object(AUTO_NC, "ID_PASTA_DRIVE_CERTIFICADOS", ""), \
                patch.object(AUTO_NC, "ID_PASTA_DRIVE_RELATORIO", ""):
            with self.assertRaises(RuntimeError) as contexto:
                AUTO_NC.executar_automacao_sieg_cadastro_a1()
        mensagem = str(contexto.exception)
        self.assertIn("GOOGLE_DRIVE_FOLDER_ID", mensagem)
        self.assertIn("AUTO_NC_REPORT_FOLDER_ID", mensagem)

    def test_execucao_nao_pede_id_por_input(self):
        with patch.object(AUTO_NC, "ID_PASTA_DRIVE_CERTIFICADOS", ""), \
                patch.object(AUTO_NC, "ID_PASTA_DRIVE_RELATORIO", "relatorios"), \
                patch("builtins.input") as entrada:
            with self.assertRaisesRegex(RuntimeError, "GOOGLE_DRIVE_FOLDER_ID"):
                AUTO_NC.executar_automacao_sieg_cadastro_a1()
        entrada.assert_not_called()


if __name__ == "__main__":
    unittest.main()
