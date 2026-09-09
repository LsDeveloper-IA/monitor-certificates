import os


def ler_inteiro_nao_negativo(nome, padrao=0):
    """Lê um inteiro não negativo do ambiente com mensagem de erro clara."""
    valor = os.getenv(nome, str(padrao)).strip()
    try:
        numero = int(valor)
    except ValueError as erro:
        raise ValueError(f"{nome} deve ser um número inteiro não negativo.") from erro
    if numero < 0:
        raise ValueError(f"{nome} deve ser um número inteiro não negativo.")
    return numero
