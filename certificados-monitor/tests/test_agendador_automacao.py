import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.services.agendador_automacao import AgendadorAutomacao


class ExecutorFalso:
    def __init__(self):
        self.chamadas = []

    def executar(self, atualizar_excel=False, notificacoes_teste=False):
        self.chamadas.append((atualizar_excel, notificacoes_teste))


class AgendadorAutomacaoTestCase(unittest.TestCase):
    def test_rejeita_horario_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            agendador = AgendadorAutomacao(
                ExecutorFalso(),
                Path(pasta) / "agendador.json",
            )
            with self.assertRaisesRegex(ValueError, "Horario invalido"):
                agendador.configurar(True, "25:90")

    def test_configuracao_e_persistida(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "agendador.json"
            agendador = AgendadorAutomacao(ExecutorFalso(), caminho)
            agendador.configurar(False, ["08:30", "14:30"], True)

            status = AgendadorAutomacao(ExecutorFalso(), caminho).status()

        self.assertFalse(status["ativo"])
        self.assertEqual(status["horarios"], ["08:30", "14:30"])
        self.assertTrue(status["atualizar_excel"])

    def test_executa_duas_vezes_no_mesmo_dia(self):
        with tempfile.TemporaryDirectory() as pasta:
            executor = ExecutorFalso()
            agendador = AgendadorAutomacao(
                executor,
                Path(pasta) / "agendador.json",
            )
            with patch.object(agendador, "iniciar_monitoramento"):
                agendador.configurar(True, ["09:00", "14:00"], True)

            primeira = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 9, 0)
            )
            repeticao_primeira = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 9, 5)
            )
            segunda = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 14, 0)
            )
            repeticao_segunda = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 14, 5)
            )

        self.assertTrue(primeira)
        self.assertFalse(repeticao_primeira)
        self.assertTrue(segunda)
        self.assertFalse(repeticao_segunda)
        self.assertEqual(executor.chamadas, [(True, False), (True, False)])

    def test_rejeita_horarios_iguais(self):
        with tempfile.TemporaryDirectory() as pasta:
            agendador = AgendadorAutomacao(
                ExecutorFalso(),
                Path(pasta) / "agendador.json",
            )
            with self.assertRaisesRegex(ValueError, "devem ser diferentes"):
                agendador.configurar(True, ["09:00", "09:00"])

    def test_executa_apenas_uma_vez_por_dia(self):
        with tempfile.TemporaryDirectory() as pasta:
            executor = ExecutorFalso()
            agendador = AgendadorAutomacao(
                executor,
                Path(pasta) / "agendador.json",
            )
            with patch.object(agendador, "iniciar_monitoramento"):
                agendador.configurar(True, "09:00", True)

            agora = datetime(2026, 8, 27, 9, 0)
            primeira = agendador._verificar_agendamento(agora)
            segunda = agendador._verificar_agendamento(agora)

        self.assertTrue(primeira)
        self.assertFalse(segunda)
        self.assertEqual(executor.chamadas, [(True, False)])

    def test_recupera_execucao_perdida_apos_horario(self):
        with tempfile.TemporaryDirectory() as pasta:
            executor = ExecutorFalso()
            agendador = AgendadorAutomacao(
                executor,
                Path(pasta) / "agendador.json",
            )
            with patch.object(agendador, "iniciar_monitoramento"):
                agendador.configurar(True, "09:00", False)

            executou = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 9, 15)
            )

        self.assertTrue(executou)
        self.assertEqual(executor.chamadas, [(False, False)])

    def test_novo_horario_pode_executar_no_mesmo_dia(self):
        with tempfile.TemporaryDirectory() as pasta:
            executor = ExecutorFalso()
            agendador = AgendadorAutomacao(
                executor,
                Path(pasta) / "agendador.json",
            )
            with patch.object(agendador, "iniciar_monitoramento"):
                agendador.configurar(True, "09:00", False)
            agendador._verificar_agendamento(datetime(2026, 8, 27, 9, 0))

            with patch.object(agendador, "iniciar_monitoramento"):
                agendador.configurar(True, "10:00", False)
            executou_novamente = agendador._verificar_agendamento(
                datetime(2026, 8, 27, 10, 0)
            )

        self.assertTrue(executou_novamente)
        self.assertEqual(executor.chamadas, [(False, False), (False, False)])

    def test_bloqueia_notificacoes_sem_destino_de_teste(self):
        with tempfile.TemporaryDirectory() as pasta:
            agendador = AgendadorAutomacao(
                ExecutorFalso(),
                Path(pasta) / "agendador.json",
            )
            with patch.dict(
                "os.environ",
                {
                    "WHATSCONTABIL_URL": "",
                    "WHATSCONTABIL_TOKEN": "",
                    "WHATSCONTABIL_NUMERO_TESTE": "",
                    "WHATSCONTABIL_WHATSAPP_ID": "",
                },
            ):
                with self.assertRaisesRegex(ValueError, "sem configuracao"):
                    agendador.configurar(True, "09:00", False, True)

    def test_encaminha_notificacoes_somente_quando_habilitadas(self):
        with tempfile.TemporaryDirectory() as pasta:
            executor = ExecutorFalso()
            agendador = AgendadorAutomacao(
                executor,
                Path(pasta) / "agendador.json",
            )
            ambiente = {
                "WHATSCONTABIL_URL": "https://teste.invalid",
                "WHATSCONTABIL_TOKEN": "token-teste",
                "WHATSCONTABIL_NUMERO_TESTE": "5585999999999",
                "WHATSCONTABIL_WHATSAPP_ID": "2",
            }
            with patch.dict("os.environ", ambiente), patch.object(
                agendador,
                "iniciar_monitoramento",
            ):
                agendador.configurar(True, "09:00", False, True)

            agendador._verificar_agendamento(datetime(2026, 8, 27, 9, 0))

        self.assertEqual(executor.chamadas, [(False, True)])


if __name__ == "__main__":
    unittest.main()
