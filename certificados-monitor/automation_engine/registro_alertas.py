import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    from utils.caminhos import obter_pasta_aplicacao
except ModuleNotFoundError:  # Importacao pelo backend e pelos testes.
    from automation_engine.utils.caminhos import obter_pasta_aplicacao


CAMINHO_REGISTRO = (
    obter_pasta_aplicacao() / "dados" / "alertas_enviados.sqlite3"
)


@contextmanager
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
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS historico_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            arquivo TEXT NOT NULL,
            dias INTEGER,
            vencimento TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            tipo TEXT NOT NULL,
            status TEXT NOT NULL,
            motivo TEXT,
            registrado_em TEXT NOT NULL
        )
        """
    )
    try:
        yield conexao
        conexao.commit()
    finally:
        conexao.close()


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


def registrar_evento_envio(alerta, tipo, status, motivo=None):
    """Registra tentativas que nao resultaram em um novo envio confirmado."""
    status_validos = {"falhou", "duplicado", "interrompido"}
    if status not in status_validos:
        raise ValueError("Status de historico invalido")
    with _abrir_registro() as conexao:
        conexao.execute(
            """
            INSERT INTO historico_envios (
                cnpj, arquivo, dias, vencimento, destinatario,
                tipo, status, motivo, registrado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alerta.get("cnpj") or "",
                alerta.get("arquivo") or "",
                alerta.get("dias"),
                str(alerta.get("vencimento") or ""),
                alerta.get("email") or "",
                tipo,
                status,
                str(motivo or "")[:1000],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def listar_alertas_enviados(limite=100):
    """Lista sucessos e tentativas sem expor o destinatario completo."""
    limite = max(1, min(int(limite), 500))
    with _abrir_registro() as conexao:
        conexao.row_factory = sqlite3.Row
        linhas = conexao.execute(
            """
            SELECT id, cnpj, arquivo, dias, vencimento, destinatario, enviado_em
            FROM alertas_enviados
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
        eventos = conexao.execute(
            """
            SELECT id, cnpj, arquivo, dias, vencimento, destinatario,
                   tipo, status, motivo, registrado_em
            FROM historico_envios
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()

    historico = []
    for linha in linhas:
        destino = linha["destinatario"] or ""
        partes = destino.split(":")
        tipo = partes[1].replace("_teste", "") if len(partes) >= 3 else "email"
        valor_destino = partes[-1] if partes else destino
        digitos = "".join(caractere for caractere in valor_destino if caractere.isdigit())
        if len(digitos) >= 4:
            destino_mascarado = f"***{digitos[-4:]}"
        elif "@" in valor_destino:
            usuario, dominio = valor_destino.split("@", 1)
            destino_mascarado = f"{usuario[:2]}***@{dominio}"
        else:
            destino_mascarado = "Protegido"

        historico.append({
            "id": linha["id"],
            "cnpj": linha["cnpj"],
            "arquivo": linha["arquivo"],
            "dias": linha["dias"],
            "vencimento": linha["vencimento"],
            "tipo": tipo,
            "destinatario": destino_mascarado,
            "enviado_em": linha["enviado_em"],
            "status": "enviado",
            "motivo": "Aceito pela WhatsContabil",
        })
    for linha in eventos:
        historico.append({
            "id": f"evento-{linha['id']}",
            "cnpj": linha["cnpj"],
            "arquivo": linha["arquivo"],
            "dias": linha["dias"],
            "vencimento": linha["vencimento"],
            "tipo": linha["tipo"],
            "destinatario": _mascarar_destinatario(linha["destinatario"]),
            "enviado_em": linha["registrado_em"],
            "status": linha["status"],
            "motivo": linha["motivo"] or "",
        })
    historico.sort(key=lambda item: item["enviado_em"], reverse=True)
    return historico[:limite]


def _mascarar_destinatario(destino):
    destino = str(destino or "")
    partes = destino.split(":")
    valor = partes[-1] if partes else destino
    digitos = "".join(caractere for caractere in valor if caractere.isdigit())
    if len(digitos) >= 4:
        return f"***{digitos[-4:]}"
    if "@" in valor:
        usuario, dominio = valor.split("@", 1)
        return f"{usuario[:2]}***@{dominio}"
    return "Protegido"
