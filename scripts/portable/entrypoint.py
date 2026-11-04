"""Inicializador do pacote portatil do Monitor de Certificados.

Este arquivo e o ponto de entrada do executavel gerado pelo PyInstaller. Ele:

1. cria o ``.env`` na primeira execucao e gera as chaves locais;
2. escolhe uma porta livre em ``127.0.0.1``;
3. aponta ``storage/`` para a pasta ao lado do executavel;
4. inicia o Flask com o Waitress e abre o navegador.

O frontend estatico e servido pelo proprio Flask, portanto nao e necessario
instalar Node.js na maquina de destino.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

PLACEHOLDERS = {
    "__GERAR_SECRET_KEY__": lambda: secrets.token_hex(32),
    "__GERAR_INTEGRACAO_API_KEY__": lambda: secrets.token_hex(16),
    "__GERAR_AUTOMACAO_EXECUTION_KEY__": lambda: secrets.token_hex(16),
    "__GERAR_AUTOMACAO_ADMIN_KEY__": lambda: secrets.token_hex(16),
}

HOST_PADRAO = "127.0.0.1"
PORTA_PADRAO = 5000


def pasta_aplicacao() -> Path:
    """Pasta gravavel: ao lado do .exe ou a raiz do repositorio em dev."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    configurada = os.getenv("MONITOR_APP_DIR", "").strip()
    if configurada:
        return Path(configurada).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def pasta_recursos() -> Path:
    """Pasta somente leitura com o frontend e os exemplos empacotados."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    configurada = os.getenv("MONITOR_RESOURCES_DIR", "").strip()
    if configurada:
        return Path(configurada).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _localizar_modelo_env() -> Path:
    candidatos = [
        pasta_recursos() / ".env.example",
        Path(__file__).resolve().parent / "env.example",
    ]
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    raise SystemExit(
        "Arquivo .env.example nao encontrado. Reinstale o pacote portatil."
    )


def preparar_env(app_dir: Path) -> Path:
    """"Cria/atualiza o .env e devolve o caminho."""
    env_file = app_dir / ".env"
    if not env_file.is_file():
        shutil.copyfile(_localizar_modelo_env(), env_file)

    texto = env_file.read_text(encoding="utf-8")
    alterou = False
    for marcador, gerar in PLACEHOLDERS.items():
        if marcador in texto:
            texto = texto.replace(marcador, gerar())
            alterou = True
    if alterou:
        env_file.write_text(texto, encoding="utf-8")
    return env_file


def carregar_env(env_file: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # Nao sobrescreve valores definidos explicitamente no ambiente do Windows.
    load_dotenv(env_file, override=False)


def _porta_livre(host: str, preferida: int) -> int | None:
    candidatas = [preferida, *range(5001, 5100)]
    vistas = set()
    for porta in candidatas:
        if porta in vistas:
            continue
        vistas.add(porta)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soquete:
            # No Windows, SO_REUSEADDR permitiria "reservar" uma porta que ja
            # esta em uso por outro processo. Sem ele, o bind falha e a
            # proxima porta e testada.
            try:
                soquete.bind((host, porta))
            except OSError:
                continue
            return porta
    return None


def _inteiro(valor: str, padrao: int) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def _endereco_navegador(host: str, porta: int) -> str:
    visivel = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    return f"http://{visivel}:{porta}"


def _configurar_caminhos(app_dir: Path, recursos: Path) -> tuple[str, int, Path]:
    env_file = preparar_env(app_dir)
    carregar_env(env_file)

    host = os.getenv("FLASK_HOST", HOST_PADRAO).strip() or HOST_PADRAO
    porta_preferida = _inteiro(os.getenv("FLASK_PORT", str(PORTA_PADRAO)), PORTA_PADRAO)
    porta = _porta_livre(host, porta_preferida)
    if porta is None:
        raise SystemExit(
            "Nao foi encontrada uma porta livre entre 5000 e 5099. "
            "Feche outros programas e tente novamente."
        )

    storage = Path(os.getenv("STORAGE_DIR", "").strip() or (app_dir / "storage"))
    if not storage.is_absolute():
        storage = (app_dir / storage).resolve()
    storage.mkdir(parents=True, exist_ok=True)

    os.environ.update(
        {
            "FLASK_HOST": host,
            "FLASK_PORT": str(porta),
            "FLASK_DEBUG": "false",
            "STORAGE_DIR": str(storage),
            "MONITOR_APP_DIR": str(app_dir),
            "MONITOR_WEB_DIR": os.getenv(
                "MONITOR_WEB_DIR", str(recursos / "web")
            ),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )

    endereco = _endereco_navegador(host, porta)
    # O frontend e as automacoes falam com esta mesma instancia.
    os.environ["FRONTEND_ORIGIN"] = endereco
    os.environ["API_MONITOR_URL"] = endereco
    return host, porta, storage


def main() -> None:
    app_dir = pasta_aplicacao()
    app_dir.mkdir(parents=True, exist_ok=True)
    recursos = pasta_recursos()

    # Em desenvolvimento, o pacote src/ fica em certificados-monitor/.
    raiz_backend = Path(__file__).resolve().parents[2] / "certificados-monitor"
    if raiz_backend.is_dir() and not getattr(sys, "frozen", False):
        if str(raiz_backend) not in sys.path:
            sys.path.insert(0, str(raiz_backend))
    if str(Path(__file__).resolve().parents[2]) not in sys.path and not getattr(
        sys, "frozen", False
    ):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    host, porta, storage = _configurar_caminhos(app_dir, recursos)
    endereco = _endereco_navegador(host, porta)

    print("=" * 62)
    print(" Monitor de Certificados")
    print("=" * 62)
    print(f" Endereco: {endereco}")
    print(f" Dados:    {storage}")
    print(" Mantenha esta janela aberta. Pressione Ctrl+C para encerrar.")
    print("=" * 62, flush=True)

    if os.getenv("MONITOR_NO_BROWSER", "").strip() != "1":
        threading.Timer(2.0, lambda: webbrowser.open(endereco)).start()

    from waitress import serve
    from src.main import app

    serve(app, host=host, port=porta, threads=8)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except Exception:
        pasta_logs = pasta_aplicacao() / "storage" / "logs"
        pasta_logs.mkdir(parents=True, exist_ok=True)
        arquivo_log = pasta_logs / "erro-inicializacao.log"
        arquivo_log.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"\nFalha ao iniciar. Detalhes em: {arquivo_log}")
        traceback.print_exc()
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:
            pass
        raise
