"""Apresentacao consistente e legivel das mensagens do terminal."""

try:
    from rich.console import Console
    from rich.progress import track
    from rich.table import Table
except ImportError:  # Permite executar antes de instalar as dependencias.
    Console = None
    track = None
    Table = None


_console = Console(highlight=False) if Console else None


def escrever(*valores, **opcoes):
    """Imprime uma mensagem com uma cor coerente com seu conteudo."""
    texto = " ".join(str(valor) for valor in valores)
    texto_normalizado = texto.casefold()

    if not _console:
        print(*valores, **opcoes)
        return

    if any(palavra in texto_normalizado for palavra in ("erro", "falha")):
        estilo = "bold red"
    elif any(
        palavra in texto_normalizado
        for palavra in ("atenção", "cancelado", "não encontrado", "bloqueado")
    ):
        estilo = "yellow"
    elif any(
        palavra in texto_normalizado
        for palavra in ("sucesso", "concluí", "enviado", "gerada", "atualizadas")
    ):
        estilo = "green"
    elif texto and (texto.isupper() or texto.endswith("...")):
        estilo = "bold cyan"
    else:
        estilo = None

    _console.print(texto, style=estilo, markup=False)


def titulo(texto):
    """Mostra um titulo destacado sem depender de linhas de separacao."""
    if _console:
        _console.rule(f"[bold cyan]{texto}[/bold cyan]")
    else:
        print(f"\n{'=' * 60}\n{texto}\n{'=' * 60}")


def tabela(titulo_tabela, colunas, linhas):
    """Exibe dados relacionados em uma tabela compacta."""
    if not _console or not Table:
        print(f"\n{titulo_tabela}")
        print(" | ".join(colunas))
        for linha in linhas:
            print(" | ".join(str(valor) for valor in linha))
        return

    componente = Table(
        title=titulo_tabela,
        header_style="bold cyan",
        border_style="dim cyan",
        show_lines=True,
        row_styles=("", "on grey7"),
        pad_edge=False,
    )
    for coluna in colunas:
        componente.add_column(str(coluna))
    for linha in linhas:
        componente.add_row(*(str(valor) for valor in linha))
    _console.print()
    _console.print(componente)


def progresso(iteravel, descricao, total=None):
    """Adiciona uma barra de progresso e mantem fallback sem a Rich."""
    if _console and track:
        return track(
            iteravel,
            description=f"[cyan]{descricao}[/cyan]",
            total=total,
            console=_console,
        )
    return iteravel
