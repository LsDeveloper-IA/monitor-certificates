import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path


class ExecutorAutomacao:
    def __init__(self):
        self._lock = threading.Lock()
        self._processo = None
        self._logs = deque(maxlen=300)
        self._inicio = None
        self._fim = None
        self._codigo_saida = None
        self._erro = None

    @property
    def pasta_motor(self):
        return Path(__file__).resolve().parents[2] / "automation_engine"

    def _registrar(self, mensagem):
        texto = str(mensagem).rstrip()
        if texto:
            with self._lock:
                self._logs.append(texto)

    def executar(self, atualizar_excel=False):
        with self._lock:
            if self._processo is not None and self._processo.poll() is None:
                raise RuntimeError("A automacao ja esta em execucao")
            self._logs.clear()
            self._inicio = datetime.now()
            self._fim = None
            self._codigo_saida = None
            self._erro = None

        threading.Thread(
            target=self._executar_processo,
            args=(atualizar_excel,),
            daemon=True,
        ).start()

    def _executar_processo(self, atualizar_excel):
        ambiente = os.environ.copy()
        ambiente.update(
            {
                "MODO_AUTOMATICO": "sim",
                "ATUALIZAR_EXCEL_AUTOMATICO": "sim" if atualizar_excel else "nao",
                "SINCRONIZAR_API_AUTOMATICO": "sim",
                "ENVIAR_EMAIL_AUTOMATICO": "nao",
                "ENVIAR_WHATSCONTABIL_AUTOMATICO": "nao",
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

    def status(self):
        with self._lock:
            executando = self._processo is not None and self._processo.poll() is None
            return {
                "executando": executando,
                "inicio": self._inicio.isoformat() if self._inicio else None,
                "fim": self._fim.isoformat() if self._fim else None,
                "codigo_saida": self._codigo_saida,
                "erro": self._erro,
                "logs": list(self._logs),
            }


executor_automacao = ExecutorAutomacao()
