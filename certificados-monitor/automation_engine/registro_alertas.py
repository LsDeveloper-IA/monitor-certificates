import sqlite3
from datetime import datetime
from pathlib import Path

from utils.caminhos import obter_pasta_aplicacao


CAMINHO_REGISTRO = (
    obter_pasta_aplicacao() / "dados" / "alertas_enviados.sqlite3"
)


def _abrir_registro():
    """Abre o banco local usado somente para controlar duplicidades."""
    CAMINHO_REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_REGISTRO)
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS alertas_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            dias INTEGER NOT NULL,
            vencimento TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            enviado_em TEXT NOT NULL,
            UNIQUE(cnpj, arquivo, dias, vencimento, destinatario)
        )
        """
    )
    return conexao


def alerta_ja_enviado(alerta):
    """Verifica se o mesmo alerta já foi enviado ao destinatário."""
    vencimento = str(alerta.get("vencimento") or "")

    with _abrir_registro() as conexao:
        resultado = conexao.execute(
            """
            SELECT 1
            FROM alertas_enviados
            WHERE cnpj = ?
              AND arquivo = ?
              AND dias = ?
              AND vencimento = ?
              AND destinatario = ?
            """,
            (
                alerta.get("cnpj") or "",
                alerta.get("arquivo") or "",
                alerta.get("dias"),
                vencimento,
                alerta.get("email") or "",
            ),
        ).fetchone()

    return resultado is not None


def alerta_ja_possui_algum_envio(alerta):
    """Verifica se o certificado já teve qualquer aviso ao destinatário.

    Diferente de ``alerta_ja_enviado``, esta consulta ignora a quantidade de
    dias. Ela é usada para não repetir diariamente o aviso de recuperação.
    """
    vencimento = str(alerta.get("vencimento") or "")

    with _abrir_registro() as conexao:
        resultado = conexao.execute(
            """
            SELECT 1
            FROM alertas_enviados
            WHERE cnpj = ?
              AND arquivo = ?
              AND vencimento = ?
              AND destinatario = ?
            LIMIT 1
            """,
            (
                alerta.get("cnpj") or "",
                alerta.get("arquivo") or "",
                vencimento,
                alerta.get("email") or "",
            ),
        ).fetchone()

    return resultado is not None


def registrar_alerta_enviado(alerta):
    """Registra localmente um alerta somente depois de um envio confirmado."""
    vencimento = str(alerta.get("vencimento") or "")

    with _abrir_registro() as conexao:
        conexao.execute(
            """
            INSERT OR IGNORE INTO alertas_enviados (
                cnpj,
                arquivo,
                dias,
                vencimento,
                destinatario,
                enviado_em
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alerta.get("cnpj") or "",
                alerta.get("arquivo") or "",
                alerta.get("dias"),
                vencimento,
                alerta.get("email") or "",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
