import json
import os
import re
import subprocess
import sys
import threading
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values


class ExecutorAutomacao:
    _ETAPAS_PROGRESSO = (
        ("consultando dados dos clientes", "Consultando dados dos clientes", 45),
        ("sincroniza", "Sincronizando certificados com o painel", 65),
        ("alertas de 30 ou 15 dias", "Preparando alertas e relatorios", 78),
        ("avisos de clientes entre", "Preparando notificacoes de teste", 84),
        ("templates preparados", "Enviando notificacoes de teste", 90),
        ("template de ", "Enviando notificacoes de teste", 94),
        ("relatorio final da automacao", "Finalizando relatorio da execucao", 98),
    )
    _PADROES_RESUMO_ENVIOS = {
        "Alertas enviados:": "email_enviados",
        "Alertas duplicados ignorados:": "email_duplicados",
        "Falhas de envio:": "email_falhas",
        "Alertas internos enviados pela WhatsContábil:": "whatscontabil_enviados",
        "Alertas internos duplicados ignorados:": "whatscontabil_duplicados",
        "Falhas de envio pela WhatsContábil:": "whatscontabil_falhas",
        "Mensagens da WhatsContábil não tentadas por segurança:": (
            "whatscontabil_interrompidos"
        ),
    }

    def __init__(self, arquivo_historico=None, pasta_motor=None):
        self._lock = threading.Lock()
        self._processo = None
        self._executando = False
        self._logs = deque(maxlen=300)
        self._inicio = None
        self._fim = None
        self._codigo_saida = None
        self._erro = None
        self._interrompida = False
        self._execucao_id = None
        self._atualizar_excel = False
        self._notificacoes_teste = False
        self._escopo_notificacoes_teste = "nenhum"
        self._forcar_reenvio_teste = False
        self._resumo_envios = self._novo_resumo_envios()
        self._etapa = "Aguardando nova execucao"
        self._progresso = 0
        self._arquivo_log_execucao = None
        self._pasta_motor_personalizada = Path(pasta_motor) if pasta_motor else None
        self._arquivo_historico = (
            Path(arquivo_historico)
            if arquivo_historico
            else Path(__file__).resolve().parents[2]
            / "runtime"
            / "historico_automacao.json"
        )
        self._historico = deque(self._carregar_historico(), maxlen=20)

    @staticmethod
    def _novo_resumo_envios():
        return {
            "email_enviados": 0,
            "email_duplicados": 0,
            "email_falhas": 0,
            "whatscontabil_enviados": 0,
            "whatscontabil_duplicados": 0,
            "whatscontabil_falhas": 0,
            "whatscontabil_interrompidos": 0,
        }

    @property
    def pasta_motor(self):
        if self._pasta_motor_personalizada:
            return self._pasta_motor_personalizada
        return Path(__file__).resolve().parents[2] / "automation_engine"

    @property
    def arquivo_env(self):
        return Path(__file__).resolve().parents[2] / ".env"

    def _montar_ambiente_execucao(
        self,
        atualizar_excel,
        notificacoes_teste,
        escopo_notificacoes_teste="completo",
        forcar_reenvio_teste=False,
    ):
        ambiente = os.environ.copy()
        configuracao_atual = dotenv_values(self.arquivo_env)
        ambiente.update({
            str(chave): str(valor)
            for chave, valor in configuracao_atual.items()
            if valor is not None
        })
        ambiente.update(
            {
                "MODO_AUTOMATICO": "sim",
                "ATUALIZAR_EXCEL_AUTOMATICO": "sim" if atualizar_excel else "nao",
                "SINCRONIZAR_API_AUTOMATICO": "sim",
                "ENVIAR_EMAIL_AUTOMATICO": "nao",
                "ENVIAR_WHATSCONTABIL_AUTOMATICO": (
                    "sim" if notificacoes_teste else "nao"
                ),
                "IGNORAR_DUPLICIDADE_WHATSCONTABIL_TESTE": (
                    "sim" if forcar_reenvio_teste else "nao"
                ),
                "WHATSCONTABIL_ESCOPO_ENVIO_TESTE": (
                    escopo_notificacoes_teste if notificacoes_teste else "nenhum"
                ),
                "MODO_WHATSCONTABIL": "teste",
                "WHATSCONTABIL_PERMITIR_NUMEROS_REAIS": "nao",
                "PYTHONUNBUFFERED": "1",
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        return ambiente

    def _carregar_historico(self):
        try:
            with self._arquivo_historico.open("r", encoding="utf-8") as arquivo:
                conteudo = json.load(arquivo)
            return conteudo if isinstance(conteudo, list) else []
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return []

    def _salvar_historico(self, registros):
        self._arquivo_historico.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._arquivo_historico.with_suffix(".tmp")
        with temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(registros, arquivo, ensure_ascii=False, indent=2)
        os.replace(temporario, self._arquivo_historico)

    def _resumo_sem_logs(self):
        executando = self._executando
        fim_calculo = self._fim or (datetime.now() if self._inicio else None)
        duracao_segundos = (
            int((fim_calculo - self._inicio).total_seconds())
            if self._inicio and fim_calculo
            else None
        )
        if executando:
            estado = "executando"
        elif self._interrompida:
            estado = "interrompida"
        elif self._codigo_saida == 0:
            estado = "concluida"
        elif self._codigo_saida is not None:
            estado = "falhou"
        else:
            estado = "aguardando"
        return {
            "id": self._execucao_id,
            "executando": executando,
            "estado": estado,
            "inicio": self._inicio.isoformat() if self._inicio else None,
            "fim": self._fim.isoformat() if self._fim else None,
            "duracao_segundos": duracao_segundos,
            "codigo_saida": self._codigo_saida,
            "erro": self._erro,
            "atualizou_excel": self._atualizar_excel,
            "notificacoes_teste": self._notificacoes_teste,
            "escopo_notificacoes_teste": self._escopo_notificacoes_teste,
            "forcou_reenvio_teste": self._forcar_reenvio_teste,
            "resumo_envios": dict(self._resumo_envios),
            "etapa": self._etapa,
            "progresso": self._progresso,
            "arquivo_log": (
                self._arquivo_log_execucao.name
                if self._arquivo_log_execucao
                else None
            ),
        }

    def _registrar_historico(self):
        with self._lock:
            registro = self._resumo_sem_logs()
            if not registro["id"] or registro["executando"]:
                return
            self._historico.appendleft(registro)
            registros = list(self._historico)
        try:
            self._salvar_historico(registros)
        except OSError as erro:
            self._registrar(f"AVISO: historico nao foi salvo: {erro}")

    def _registrar(self, mensagem):
        texto = str(mensagem).rstrip()
        if texto:
            with self._lock:
                self._logs.append(texto)
                arquivo_log = self._arquivo_log_execucao
                texto_limpo = re.sub(r"\x1b\[[0-9;]*m", "", texto)
                texto_busca = texto_limpo.casefold()
                for marcador, etapa, progresso in self._ETAPAS_PROGRESSO:
                    if marcador in texto_busca and progresso >= self._progresso:
                        self._etapa = etapa
                        self._progresso = progresso
                for rotulo, campo in self._PADROES_RESUMO_ENVIOS.items():
                    encontrado = re.search(
                        rf"{re.escape(rotulo)}\s*(\d+)",
                        texto_limpo,
                        flags=re.IGNORECASE,
                    )
                    if encontrado:
                        self._resumo_envios[campo] = int(encontrado.group(1))
            if arquivo_log:
                try:
                    with arquivo_log.open("a", encoding="utf-8") as arquivo:
                        arquivo.write(f"{texto_limpo}\n")
                except OSError:
                    # O acompanhamento em memoria continua funcionando mesmo
                    # se o arquivo local estiver temporariamente indisponivel.
                    pass

    def executar(
        self,
        atualizar_excel=False,
        notificacoes_teste=False,
        escopo_notificacoes_teste="completo",
        forcar_reenvio_teste=False,
    ):
        with self._lock:
            if self._executando:
                raise RuntimeError("A automacao ja esta em execucao")
            self._executando = True
            self._logs.clear()
            self._inicio = datetime.now()
            self._fim = None
            self._codigo_saida = None
            self._erro = None
            self._interrompida = False
            self._execucao_id = uuid.uuid4().hex
            pasta_logs = self._arquivo_historico.parent / "execucoes"
            pasta_logs.mkdir(parents=True, exist_ok=True)
            self._arquivo_log_execucao = (
                pasta_logs / f"execucao-{self._execucao_id}.log"
            )
            self._atualizar_excel = atualizar_excel
            self._notificacoes_teste = notificacoes_teste
            self._escopo_notificacoes_teste = (
                escopo_notificacoes_teste if notificacoes_teste else "nenhum"
            )
            self._forcar_reenvio_teste = bool(
                forcar_reenvio_teste and notificacoes_teste
            )
            self._resumo_envios = self._novo_resumo_envios()
            self._etapa = "Iniciando processamento"
            self._progresso = 5

        try:
            threading.Thread(
                target=self._executar_processo,
                args=(
                    atualizar_excel,
                    notificacoes_teste,
                    self._escopo_notificacoes_teste,
                    self._forcar_reenvio_teste,
                ),
                daemon=True,
            ).start()
        except Exception as erro:
            with self._lock:
                self._executando = False
                self._fim = datetime.now()
                self._codigo_saida = -1
                self._erro = str(erro)
            self._registrar_historico()
            raise

    def parar(self):
        with self._lock:
            processo = self._processo
            if not self._executando or processo is None:
                return False
            self._interrompida = True
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                processo.terminate()
        return True

    def _executar_processo(
        self,
        atualizar_excel,
        notificacoes_teste,
        escopo_notificacoes_teste,
        forcar_reenvio_teste,
    ):
        ambiente = self._montar_ambiente_execucao(
            atualizar_excel,
            notificacoes_teste,
            escopo_notificacoes_teste,
            forcar_reenvio_teste,
        )
        try:
            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

            processo = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=self.pasta_motor,
                env=ambiente,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                start_new_session=(os.name != "nt"),
            )
            with self._lock:
                self._processo = processo
            if processo.stdout:
                for linha in processo.stdout:
                    self._registrar(linha)
            codigo = processo.wait()
            with self._lock:
                self._codigo_saida = codigo
                if codigo != 0 and not self._interrompida:
                    self._erro = f"Automacao encerrada com codigo {codigo}"
                    self._etapa = "Execucao encerrada com erro"
                else:
                    self._etapa = "Processamento concluido"
                    self._progresso = 100
        except Exception as erro:
            with self._lock:
                self._codigo_saida = -1
                self._erro = str(erro)
                self._etapa = "Falha ao executar a automacao"
            self._registrar(f"ERRO: {erro}")
        finally:
            with self._lock:
                self._fim = datetime.now()
                self._processo = None
                self._executando = False
            self._registrar_historico()

    def status(self):
        with self._lock:
            return {
                **self._resumo_sem_logs(),
                "logs": list(self._logs),
            }

    def historico(self):
        with self._lock:
            return list(self._historico)


executor_automacao = ExecutorAutomacao()
executor_sieg_automacao = ExecutorAutomacao(
    arquivo_historico=Path(__file__).resolve().parents[2] / "runtime" / "historico_sieg.json",
    pasta_motor=Path(__file__).resolve().parents[3] / "automacao-sieg",
)
