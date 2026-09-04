try:
    from .conexao import ErroConexaoBanco, conectar_banco
except ImportError:  # Compatibilidade com a execuÃ§Ã£o direta da automaÃ§Ã£o.
    from banco.conexao import ErroConexaoBanco, conectar_banco


__all__ = ["ErroConexaoBanco", "conectar_banco"]
