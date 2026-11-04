import os
import unittest
from unittest.mock import patch

from sieg_comum.configuracao import ler_inteiro_nao_negativo


class ConfiguracaoTest(unittest.TestCase):
    def test_atraso_padrao_e_zero(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ler_inteiro_nao_negativo("SIEG_SLOW_MO_MS"), 0)

    def test_permite_cinquenta_milissegundos(self):
        with patch.dict(os.environ, {"SIEG_SLOW_MO_MS": "50"}, clear=True):
            self.assertEqual(ler_inteiro_nao_negativo("SIEG_SLOW_MO_MS"), 50)

    def test_rejeita_valores_invalidos(self):
        for valor in ("-1", "abc", "2.5"):
            with self.subTest(valor=valor), patch.dict(
                os.environ, {"SIEG_SLOW_MO_MS": valor}, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "inteiro não negativo"):
                    ler_inteiro_nao_negativo("SIEG_SLOW_MO_MS")


if __name__ == "__main__":
    unittest.main()
