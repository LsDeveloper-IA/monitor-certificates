try:
    from .conexao import ErroConexaoBanco, conectar_banco
except ImportError:  # Compatibilidade com a execução direta da automação.
    from banco.conexao import ErroConexaoBanco, conectar_banco


__all__ = ["ErroConexaoBanco", "conectar_banco"]
