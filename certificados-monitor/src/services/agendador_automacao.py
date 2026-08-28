import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from src.services.executor_automacao import executor_automacao


class AgendadorAutomacao:
    def __init__(self, executor=None, arquivo_configuracao=None):
        self._executor = executor or executor_automacao
        self._arquivo = (
            Path(arquivo_configuracao)
            if arquivo_configuracao
            else Path(__file__).resolve().parents[2]
            / "runtime"
            / "agendador_automacao.json"
        )
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread = None
        self._configuracao = {
            "ativo": False,
            "horarios": ["09:00", "14:00"],
            "atualizar_excel": False,
            "notificacoes_teste": False,
            "ultima_tentativa_data": None,
            "ultima_tentativa_horario": None,
            "horarios_tentados": [],
            "ultima_execucao": None,
            "ultimo_erro": None,
        }
        self._carregar()

    def _carregar(self):
        try:
            with self._arquivo.open("r", encoding="utf-8") as arquivo:
                conteudo = json.load(arquivo)
            if isinstance(conteudo, dict):
                if "horarios" not in conteudo and conteudo.get("horario"):
                    primeiro = conteudo["horario"]
                    segundo = "14:00" if primeiro != "14:00" else "09:00"
                    conteudo["horarios"] = sorted([primeiro, segundo])
                conteudo.pop("horario", None)
                self._configuracao.update(conteudo)
                if (
                    not self._configuracao.get("horarios_tentados")
                    and self._configuracao.get("ultima_tentativa_horario")
                ):
                    self._configuracao["horarios_tentados"] = [
                        self._configuracao["ultima_tentativa_horario"]
                    ]
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass

    def _salvar(self, configuracao):
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._arquivo.with_suffix(".tmp")
        with temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(configuracao, arquivo, ensure_ascii=False, indent=2)
        os.replace(temporario, self._arquivo)

    @staticmethod
    def _validar_horario(horario):
        try:
            datetime.strptime(horario, "%H:%M")
        except (TypeError, ValueError) as erro:
            raise ValueError("Horario invalido. Use o formato HH:MM") from erro

    def configurar(
        self,
        ativo,
        horarios,
        atualizar_excel=False,
        notificacoes_teste=False,
    ):
        if isinstance(horarios, str):
            horarios = [horarios, "14:00" if horarios != "14:00" else "09:00"]
        if not isinstance(horarios, list) or len(horarios) != 2:
            raise ValueError("Informe exatamente dois horarios diarios")
        horarios = sorted(str(horario).strip() for horario in horarios)
        for horario in horarios:
            self._validar_horario(horario)
        if horarios[0] == horarios[1]:
            raise ValueError("Os dois horarios devem ser diferentes")
        if notificacoes_teste:
            obrigatorias = (
                "WHATSCONTABIL_URL",
                "WHATSCONTABIL_TOKEN",
                "WHATSCONTABIL_NUMERO_TESTE",
                "WHATSCONTABIL_WHATSAPP_ID",
            )
            ausentes = [nome for nome in obrigatorias if not os.getenv(nome, "").strip()]
            if ausentes:
                raise ValueError(
                    "Notificacoes de teste sem configuracao: " + ", ".join(ausentes)
                )
        with self._lock:
            self._configuracao.update(
                {
                    "ativo": ativo is True,
                    "horarios": horarios,
                    "atualizar_excel": atualizar_excel is True,
                    "notificacoes_teste": notificacoes_teste is True,
                    "ultimo_erro": None,
                }
            )
            configuracao = dict(self._configuracao)
        self._salvar(configuracao)
        if configuracao["ativo"]:
            self.iniciar_monitoramento()
        self._parar.set()
        return self.status()

    def iniciar_monitoramento(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._parar.clear()
            self._thread = threading.Thread(
                target=self._monitorar,
                name="agendador-automacao",
                daemon=True,
            )
            self._thread.start()

    def _monitorar(self):
        while True:
            self._verificar_agendamento()
            self._parar.wait(15)
            self._parar.clear()

    def _verificar_agendamento(self, agora=None):
        agora = agora or datetime.now()
        data_atual = agora.date().isoformat()
        with self._lock:
            configuracao = dict(self._configuracao)
            if not configuracao["ativo"]:
                return False

            horarios_tentados = (
                list(configuracao.get("horarios_tentados") or [])
                if configuracao.get("ultima_tentativa_data") == data_atual
                else []
            )
            horario_pendente = None
            for horario in configuracao["horarios"]:
                hora, minuto = map(int, horario.split(":"))
                horario_do_dia = agora.replace(
                    hour=hora,
                    minute=minuto,
                    second=0,
                    microsecond=0,
                )
                if agora >= horario_do_dia and horario not in horarios_tentados:
                    horario_pendente = horario
                    break

            if horario_pendente is None:
                return False

            horarios_tentados.append(horario_pendente)
            self._configuracao["ultima_tentativa_data"] = data_atual
            self._configuracao["ultima_tentativa_horario"] = horario_pendente
            self._configuracao["horarios_tentados"] = horarios_tentados
            self._configuracao["ultimo_erro"] = None
            configuracao = dict(self._configuracao)
        self._salvar(configuracao)

        try:
            self._executor.executar(
                atualizar_excel=configuracao["atualizar_excel"],
                notificacoes_teste=configuracao["notificacoes_teste"],
            )
            with self._lock:
                self._configuracao["ultima_execucao"] = agora.isoformat()
                configuracao = dict(self._configuracao)
            self._salvar(configuracao)
            return True
        except RuntimeError as erro:
            with self._lock:
                # Se a automação anterior ainda estiver executando, conserva
                # este horário como pendente para tentar novamente depois.
                tentados = list(self._configuracao.get("horarios_tentados") or [])
                if horario_pendente in tentados:
                    tentados.remove(horario_pendente)
                self._configuracao["horarios_tentados"] = tentados
                self._configuracao["ultimo_erro"] = str(erro)
                configuracao = dict(self._configuracao)
            self._salvar(configuracao)
            return False

    def status(self, agora=None):
        agora = agora or datetime.now()
        with self._lock:
            configuracao = dict(self._configuracao)
            monitorando = self._thread is not None and self._thread.is_alive()

        proxima_execucao = None
        if configuracao["ativo"]:
            data_atual = agora.date().isoformat()
            tentados = (
                configuracao.get("horarios_tentados") or []
                if configuracao.get("ultima_tentativa_data") == data_atual
                else []
            )
            alvos = []
            for horario in configuracao["horarios"]:
                hora, minuto = map(int, horario.split(":"))
                alvo = agora.replace(
                    hour=hora,
                    minute=minuto,
                    second=0,
                    microsecond=0,
                )
                if horario in tentados:
                    alvo += timedelta(days=1)
                alvos.append(alvo)
            proxima_execucao = min(alvos).isoformat()

        return {
            **configuracao,
            "monitorando": monitorando,
            "proxima_execucao": proxima_execucao,
        }


agendador_automacao = AgendadorAutomacao()
