import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from src.routes.automacao import automacao_bp
from src.services.executor_automacao import ExecutorAutomacao, executor_sieg_automacao


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

    def test_saude_reconhece_templates_pdf_configurados(self):
        with patch.dict(
            os.environ,
            {
                "WHATSCONTABIL_TEMPLATE_EQUIPE_TESTE": "",
                "WHATSCONTABIL_TEMPLATE_RESPONSAVEL_TESTE": "",
                "WHATSCONTABIL_TEMPLATE_EQUIPE_DOCUMENTO_TESTE": (
                    "relatorio_pendencias_certificados"
                ),
                "WHATSCONTABIL_TEMPLATE_RESPONSAVEL_DOCUMENTO_TESTE": (
                    "relatorio_renovacoes_responsavel"
                ),
            },
            clear=False,
        ):
            resposta = self.cliente.get(
                "/api/automacao/saude",
                headers={"X-Automation-Key": "chave-interna-teste"},
            )

        integracoes = {
            item["id"]: item for item in resposta.json["integracoes"]
        }
        self.assertEqual(integracoes["template_equipe"]["estado"], "configurado")
        self.assertEqual(
            integracoes["template_responsavel"]["estado"],
            "configurado",
        )

    @patch("src.routes.automacao.Path.exists", return_value=True)
    def test_saude_reconhece_relatorios_por_link_configurados(self, _exists):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_PASTA_RELATORIOS_PDF_ID": "pasta-segura",
                "WHATSCONTABIL_TEMPLATE_RELATORIO_LINK_TESTE": (
                    "relatorio_certificados_link_"
                ),
            },
            clear=False,
        ):
            resposta = self.cliente.get(
                "/api/automacao/saude",
                headers={"X-Automation-Key": "chave-interna-teste"},
            )

        integracoes = {
            item["id"]: item for item in resposta.json["integracoes"]
        }
        self.assertEqual(integracoes["relatorios_link"]["estado"], "ok")

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
            escopo_notificacoes_teste="completo",
            forcar_reenvio_teste=False,
        )

    def test_execucao_manual_rejeita_escopo_desconhecido(self):
        resposta = self.cliente.post(
            "/api/automacao/executar",
            headers={"X-Automation-Key": "chave-interna-teste"},
            json={"escopo_notificacoes_teste": "numeros_reais"},
        )

        self.assertEqual(resposta.status_code, 400)


class ExecutorAutomacaoTestCase(unittest.TestCase):
    @patch(
        "src.services.executor_automacao.dotenv_values",
        return_value={
            "WHATSCONTABIL_TEMPLATE_EQUIPE_TESTE": "resumo_pendencias_certificados",
            "WHATSCONTABIL_TEMPLATE_RESPONSAVEL_TESTE": "resumo_renovacoes_responsavel",
            "MODO_WHATSCONTABIL": "real",
        },
    )
    def test_cada_execucao_recarrega_env_e_preserva_modo_teste(self, _dotenv):
        ambiente = ExecutorAutomacao()._montar_ambiente_execucao(
            atualizar_excel=False,
            notificacoes_teste=True,
        )

        self.assertEqual(
            ambiente["WHATSCONTABIL_TEMPLATE_EQUIPE_TESTE"],
            "resumo_pendencias_certificados",
        )
        self.assertEqual(
            ambiente["WHATSCONTABIL_TEMPLATE_RESPONSAVEL_TESTE"],
            "resumo_renovacoes_responsavel",
        )
        self.assertEqual(ambiente["MODO_WHATSCONTABIL"], "teste")
        self.assertEqual(ambiente["ATUALIZAR_EXCEL_AUTOMATICO"], "nao")
        self.assertEqual(ambiente["ENVIAR_WHATSCONTABIL_AUTOMATICO"], "sim")
        self.assertEqual(ambiente["WHATSCONTABIL_ESCOPO_ENVIO_TESTE"], "completo")
        self.assertEqual(ambiente["WHATSCONTABIL_PERMITIR_NUMEROS_REAIS"], "nao")
        self.assertEqual(
            ambiente["IGNORAR_DUPLICIDADE_WHATSCONTABIL_TESTE"],
            "nao",
        )

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
        self.assertEqual(set(status["automacoes"]), {"certificados"})
        self.assertEqual(
            status["automacoes"]["certificados"],
            {
                "nome": "Certificados",
                "estado": "aguardando",
                "codigo_saida": None,
                "logs": [],
            },
        )

    def test_status_informa_resultado_individual_dos_motores(self):
        executor = ExecutorAutomacao(
            pastas_motores=executor_sieg_automacao.pastas_motores,
            nomes_motores={
                "certificados_vencidos": "Certificados vencidos (SIEG)",
                "auto_nc": "Empresas sem certificado (Auto_NC)",
            },
        )
        executor._resultados_motores = {
            "certificados_vencidos": 0,
            "auto_nc": 1,
        }
        executor._registrar_motor("auto_nc", "Falha no cadastro")

        automacoes = executor.status()["automacoes"]

        self.assertEqual(set(automacoes), {"certificados_vencidos", "auto_nc"})
        self.assertEqual(
            automacoes["certificados_vencidos"]["nome"],
            "Certificados vencidos (SIEG)",
        )
        self.assertEqual(automacoes["certificados_vencidos"]["estado"], "concluida")
        self.assertEqual(automacoes["certificados_vencidos"]["codigo_saida"], 0)
        self.assertEqual(
            automacoes["auto_nc"]["nome"], "Empresas sem certificado (Auto_NC)"
        )
        self.assertEqual(automacoes["auto_nc"]["estado"], "falhou")
        self.assertEqual(automacoes["auto_nc"]["codigo_saida"], 1)
        self.assertEqual(automacoes["auto_nc"]["logs"], ["Falha no cadastro"])

    def test_configura_os_dois_motores_de_automacao(self):
        pasta_repositorio = Path(__file__).resolve().parents[2]
        pasta_certificados = pasta_repositorio / "certificados-monitor" / "automation_engine"
        pasta_antiga = pasta_repositorio / "automacao-sieg"
        pasta_auto_nc = pasta_repositorio / "Auto_NC"

        self.assertTrue((pasta_certificados / "main.py").exists())
        self.assertTrue((pasta_auto_nc / "main.py").exists())
        self.assertTrue((pasta_antiga / "main.py").exists())
        self.assertEqual(ExecutorAutomacao().pasta_motor, pasta_certificados)
        self.assertEqual(
            set(ExecutorAutomacao().pastas_motores),
            {"certificados"},
        )
        self.assertEqual(executor_sieg_automacao.pasta_motor, pasta_antiga)
        self.assertEqual(
            set(executor_sieg_automacao.pastas_motores),
            {"certificados_vencidos", "auto_nc"},
        )
        self.assertEqual(
            executor_sieg_automacao._ordem_motores,
            ["certificados_vencidos", "auto_nc"],
        )

    def test_executa_sieg_e_depois_auto_nc_sem_sobrepor_processos(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            pasta_sieg = raiz / "automacao-sieg"
            pasta_auto_nc = raiz / "Auto_NC"
            pasta_sieg.mkdir()
            pasta_auto_nc.mkdir()
            (pasta_sieg / "main.py").touch()
            (pasta_auto_nc / "main.py").touch()
            eventos = []
            processos_ativos = []

            class ProcessoFalso:
                stdout = []
                pid = 123

                def __init__(self, nome):
                    self.nome = nome

                def wait(self):
                    eventos.append(f"fim:{self.nome}")
                    processos_ativos.remove(self.nome)
                    return 0

            def iniciar_processo(*_args, **kwargs):
                nome = Path(kwargs["cwd"]).name
                self.assertEqual(processos_ativos, [])
                processos_ativos.append(nome)
                eventos.append(f"inicio:{nome}")
                return ProcessoFalso(nome)

            executor = ExecutorAutomacao(
                arquivo_historico=raiz / "historico.json",
                pastas_motores={
                    "certificados_vencidos": pasta_sieg,
                    "auto_nc": pasta_auto_nc,
                },
                ordem_motores=("certificados_vencidos", "auto_nc"),
            )
            executor._executando = True
            executor._execucao_id = "sequencial"
            executor._inicio = datetime.now()

            with patch(
                "src.services.executor_automacao.subprocess.Popen",
                side_effect=iniciar_processo,
            ):
                executor._executar_processo(False, False, "nenhum", False)

        self.assertEqual(
            eventos,
            [
                "inicio:automacao-sieg",
                "fim:automacao-sieg",
                "inicio:Auto_NC",
                "fim:Auto_NC",
            ],
        )

    def test_nao_inicia_auto_nc_quando_automacao_sieg_falha(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            pasta_sieg = raiz / "automacao-sieg"
            pasta_auto_nc = raiz / "Auto_NC"
            pasta_sieg.mkdir()
            pasta_auto_nc.mkdir()
            (pasta_sieg / "main.py").touch()
            (pasta_auto_nc / "main.py").touch()

            class ProcessoFalso:
                stdout = []
                pid = 123

                @staticmethod
                def wait():
                    return 1

            executor = ExecutorAutomacao(
                arquivo_historico=raiz / "historico.json",
                pastas_motores={
                    "certificados_vencidos": pasta_sieg,
                    "auto_nc": pasta_auto_nc,
                },
                ordem_motores=("certificados_vencidos", "auto_nc"),
            )
            executor._executando = True
            executor._execucao_id = "falha-sieg"
            executor._inicio = datetime.now()

            with patch(
                "src.services.executor_automacao.subprocess.Popen",
                return_value=ProcessoFalso(),
            ) as popen:
                executor._executar_processo(False, False, "nenhum", False)

            status = executor.status()

        popen.assert_called_once()
        self.assertEqual(
            status["automacoes"]["certificados_vencidos"]["estado"], "falhou"
        )
        self.assertEqual(
            status["automacoes"]["auto_nc"]["estado"], "interrompida"
        )

    def test_resumo_de_envios_e_extraido_dos_logs(self):
        executor = ExecutorAutomacao()

        executor._registrar("Alertas enviados: 3")
        executor._registrar("Alertas duplicados ignorados: 2")
        executor._registrar("Falhas de envio pela WhatsContábil: 1")
        resumo = executor.status()["resumo_envios"]

        self.assertEqual(resumo["email_enviados"], 3)
        self.assertEqual(resumo["email_duplicados"], 2)
        self.assertEqual(resumo["whatscontabil_falhas"], 1)

    def test_etapa_e_progresso_sao_extraidos_dos_logs(self):
        executor = ExecutorAutomacao()
        executor._registrar("Consultando dados dos clientes pelo CNPJ...")
        status = executor.status()

        self.assertEqual(status["etapa"], "Consultando dados dos clientes")
        self.assertEqual(status["progresso"], 45)

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
