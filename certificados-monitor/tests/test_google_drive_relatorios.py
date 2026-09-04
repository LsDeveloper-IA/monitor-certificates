import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PASTA_MOTOR = Path(__file__).resolve().parents[1] / "automation_engine"
if str(PASTA_MOTOR) not in sys.path:
    sys.path.insert(0, str(PASTA_MOTOR))

from integracoes import google_drive


class GoogleDriveRelatoriosTestCase(unittest.TestCase):
    def test_obter_link_prefere_web_view_link(self):
        link = google_drive.obter_link_relatorio({
            "id": "arquivo-1",
            "webViewLink": "https://drive.google.com/relatorio",
        })
        self.assertEqual(link, "https://drive.google.com/relatorio")

    def test_permissao_restrita_nao_chama_api(self):
        drive = Mock()
        resultado = google_drive.configurar_permissao_relatorio(
            drive,
            "arquivo-1",
            "restrito",
        )
        drive.permissions.assert_not_called()
        self.assertTrue(resultado["herdada_da_pasta"])

    @patch.object(google_drive, "conectar_google_drive_relatorios")
    def test_upload_publica_pdf_sem_torna_lo_publico(self, conectar):
        drive = conectar.return_value
        drive.files.return_value.create.return_value.execute.return_value = {
            "id": "arquivo-1",
            "name": "relatorio.pdf",
            "webViewLink": "https://drive.google.com/relatorio",
        }

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "relatorio.pdf"
            caminho.write_bytes(b"%PDF-relatorio")
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_PASTA_RELATORIOS_PDF_ID": "pasta-segura",
                    "GOOGLE_DRIVE_RELATORIOS_PERMISSAO": "restrito",
                    "GOOGLE_DRIVE_RELATORIOS_LEITOR": "",
                },
                clear=False,
            ):
                arquivo = google_drive.enviar_relatorio_drive(
                    caminho,
                    PASTA_MOTOR,
                )

        self.assertEqual(arquivo["id"], "arquivo-1")
        argumentos = drive.files.return_value.create.call_args.kwargs
        self.assertEqual(argumentos["body"]["parents"], ["pasta-segura"])
        drive.permissions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
