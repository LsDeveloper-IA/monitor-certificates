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


class ExecutorAutomacao:
    _PADROES_RESUMO_ENVIOS = {
        "Alertas enviados:": "email_enviados",
        "Alertas duplicados ignorados:": "email_duplicados",
        "Falhas de envio:": "email_falhas",
        "Alertas internos enviados pela WhatsContábil:": "whatscontabil_enviados",
        "Alertas internos duplicados ignorados:": "whatscontabil_duplicados",
        "Falhas de envio pela WhatsContábil:": "whatscontabil_falhas",
    }

    def __init__(self, arquivo_historico=None):
        self._lock = threading.Lock()
        self._processo = None
        self._executando = False
        self._logs = deque(maxlen=300)
        self._inicio = None
        self._fim = None
        self._codigo_saida = None
        self._erro = None
        self._execucao_id = None
        self._atualizar_excel = False
        self._notificacoes_teste = False
        self._resumo_envios = self._novo_resumo_envios()
        self._arquivo_log_execucao = None
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
        }

    @property
    def pasta_motor(self):
        return Path(__file__).resolve().parents[2] / "automation_engine"

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
            "resumo_envios": dict(self._resumo_envios),
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

    def executar(self, atualizar_excel=False, notificacoes_teste=False):
        with self._lock:
            if self._executando:
                raise RuntimeError("A automacao ja esta em execucao")
            self._executando = True
            self._logs.clear()
            self._inicio = datetime.now()
            self._fim = None
            self._codigo_saida = None
            self._erro = None
            self._execucao_id = uuid.uuid4().hex
            pasta_logs = self._arquivo_historico.parent / "execucoes"
            pasta_logs.mkdir(parents=True, exist_ok=True)
            self._arquivo_log_execucao = (
                pasta_logs / f"execucao-{self._execucao_id}.log"
            )
            self._atualizar_excel = atualizar_excel
            self._notificacoes_teste = notificacoes_teste
            self._resumo_envios = self._novo_resumo_envios()

        try:
            threading.Thread(
                target=self._executar_processo,
                args=(atualizar_excel, notificacoes_teste),
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

    def _executar_processo(self, atualizar_excel, notificacoes_teste):
        ambiente = os.environ.copy()
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
                    "sim" if notificacoes_teste else "nao"
                ),
                "MODO_WHATSCONTABIL": "teste",
                "PYTHONUNBUFFERED": "1",
            }
        )
        try:
            processo = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=self.pasta_motor,
                env=ambiente,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            with self._lock:
                self._processo = processo
            if processo.stdout:
                for linha in processo.stdout:
                    self._registrar(linha)
            codigo = processo.wait()
            with self._lock:
                self._codigo_saida = codigo
                if codigo != 0:
                    self._erro = f"Automacao encerrada com codigo {codigo}"
        except Exception as erro:
            with self._lock:
                self._codigo_saida = -1
                self._erro = str(erro)
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
