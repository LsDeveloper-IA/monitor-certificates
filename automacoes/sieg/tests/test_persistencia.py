import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import persistencia


class GerarResumoExecucaoTest(unittest.TestCase):
    def test_mantem_os_dez_resumos_mais_recentes(self):
        agora = datetime(2026, 9, 9, 12, 0, 0)
        arquivos = [
            {
                "id": f"id-{indice}",
                "name": f"resumo_{indice:04d}.json",
                "createdTime": (agora + timedelta(minutes=indice)).isoformat() + "Z",
            }
            for indice in range(12)
        ]
        service = Mock()
        arquivos_api = service.files.return_value
        arquivos_api.create.return_value.execute.return_value = arquivos[-1]
        arquivos_api.list.return_value.execute.return_value = {"files": arquivos}

        with patch.object(persistencia, "validar_pastas_drive"), patch.object(
            persistencia, "_agora", return_value=agora
        ):
            persistencia.gerar_resumo_execucao(
                sucessos=10,
                falhas_detalhes=[],
                ignorados=0,
                service=service,
            )

        ids_excluidos = [
            chamada.kwargs["fileId"]
            for chamada in arquivos_api.delete.call_args_list
        ]
        self.assertEqual(ids_excluidos, ["id-1", "id-0"])


if __name__ == "__main__":
    unittest.main()
