import unittest
from unittest.mock import patch

import config


class ConfigPastasTest(unittest.TestCase):
    def test_aceita_as_duas_pastas_configuradas(self):
        with patch.object(config, "DRIVE_ROOT_FOLDER_ID", "raiz"), \
                patch.object(config, "DRIVE_RELATORIOS_FOLDER_ID", "relatorios"):
            self.assertIsNone(config.validar_pastas_drive())

    def test_informa_todas_as_variaveis_ausentes(self):
        with patch.object(config, "DRIVE_ROOT_FOLDER_ID", ""), \
                patch.object(config, "DRIVE_RELATORIOS_FOLDER_ID", ""):
            with self.assertRaises(RuntimeError) as contexto:
                config.validar_pastas_drive()
        mensagem = str(contexto.exception)
        self.assertIn("DRIVE_ROOT_FOLDER_ID", mensagem)
        self.assertIn("DRIVE_RELATORIOS_FOLDER_ID", mensagem)
        self.assertIn(str(config.ARQUIVO_ENV), mensagem)


if __name__ == "__main__":
    unittest.main()
