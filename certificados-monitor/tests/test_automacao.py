import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from src.routes.automacao import automacao_bp
from src.services.executor_automacao import ExecutorAutomacao


class AutomacaoProtegidaTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["AUTOMACAO_EXECUTION_KEY"] = "chave-interna-teste"
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(automacao_bp, url_prefix="/api")
        self.cliente = app.test_client()

    def tearDown(self):
        os.environ.pop("AUTOMACAO_EXECUTION_KEY", None)

    def test_bloqueia_status_sem_chave(self):
        resposta = self.cliente.get("/api/automacao/status")
        self.assertEqual(resposta.status_code, 401)

    def test_permite_status_local_com_chave(self):
        resposta = self.cliente.get(
            "/api/automacao/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("executando", resposta.json)

    def test_bloqueia_origem_remota(self):
        resposta = self.cliente.get(
            "/api/automacao/status",
            headers={"X-Automation-Key": "chave-interna-teste"},
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )
        self.assertEqual(resposta.status_code, 401)

    def test_permite_consultar_historico(self):
        resposta = self.cliente.get(
            "/api/automacao/historico",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("execucoes", resposta.json)

    def test_permite_consultar_agendador_integrado(self):
        resposta = self.cliente.get(
            "/api/automacao/agendador-status",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json["horarios"]), 2)

    def test_saude_nao_expoe_credenciais(self):
        resposta = self.cliente.get(
            "/api/automacao/saude",
            headers={"X-Automation-Key": "chave-interna-teste"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("integracoes", resposta.json)
        conteudo = resposta.get_data(as_text=True).lower()
        self.assertNotIn("token", conteudo)
        self.assertNotIn("senha", conteudo)

    def test_rejeita_horario_invalido_no_agendador(self):
        resposta = self.cliente.post(
            "/api/automacao/agendador-configurar",
            headers={"X-Automation-Key": "chave-interna-teste"},
            json={"ativo": True, "horario": "99:99"},
        )
        self.assertEqual(resposta.status_code, 400)

    @patch("src.routes.automacao.executor_automacao.executar")
    @patch("src.routes.automacao.executor_automacao.status", return_value={})
    def test_execucao_manual_encaminha_opcao_de_notificacoes(
        self,
        _status,
        executar,
    ):
        resposta = self.cliente.post(
            "/api/automacao/executar",
            headers={"X-Automation-Key": "chave-interna-teste"},
            json={
                "atualizar_excel": True,
                "notificacoes_teste": True,
            },
        )

        self.assertEqual(resposta.status_code, 202)
        executar.assert_called_once_with(
            atualizar_excel=True,
            notificacoes_teste=True,
        )


class ExecutorAutomacaoTestCase(unittest.TestCase):
    def test_bloqueia_segunda_execucao_durante_inicializacao(self):
        executor = ExecutorAutomacao()

        with patch("src.services.executor_automacao.threading.Thread"):
            executor.executar()

            self.assertTrue(executor.status()["executando"])
            with self.assertRaisesRegex(RuntimeError, "ja esta em execucao"):
                executor.executar()

    def test_status_inicial_e_compreensivel(self):
        with tempfile.TemporaryDirectory() as pasta:
            status = ExecutorAutomacao(Path(pasta) / "historico.json").status()

        self.assertEqual(status["estado"], "aguardando")
        self.assertFalse(status["executando"])
        self.assertIsNone(status["duracao_segundos"])
        self.assertEqual(status["resumo_envios"]["email_enviados"], 0)

    def test_usa_a_automacao_sieg_quando_ela_existe(self):
        pasta_repositorio = Path(__file__).resolve().parents[2]
        pasta_sieg = pasta_repositorio / "automacao-sieg"

        self.assertTrue((pasta_sieg / "main.py").exists())
        self.assertEqual(ExecutorAutomacao().pasta_motor, pasta_sieg)

    def test_resumo_de_envios_e_extraido_dos_logs(self):
        executor = ExecutorAutomacao()

        executor._registrar("Alertas enviados: 3")
        executor._registrar("Alertas duplicados ignorados: 2")
        executor._registrar("Falhas de envio pela WhatsContábil: 1")
        resumo = executor.status()["resumo_envios"]

        self.assertEqual(resumo["email_enviados"], 3)
        self.assertEqual(resumo["email_duplicados"], 2)
        self.assertEqual(resumo["whatscontabil_falhas"], 1)

    def test_historico_e_salvo_e_recarregado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "historico.json"
            executor = ExecutorAutomacao(caminho)
            executor._execucao_id = "execucao-teste"
            executor._inicio = datetime.now()
            executor._fim = datetime.now()
            executor._codigo_saida = 0
            executor._registrar_historico()

            historico = ExecutorAutomacao(caminho).historico()

        self.assertEqual(len(historico), 1)
        self.assertEqual(historico[0]["id"], "execucao-teste")
        self.assertEqual(historico[0]["estado"], "concluida")

if __name__ == "__main__":
    unittest.main()
