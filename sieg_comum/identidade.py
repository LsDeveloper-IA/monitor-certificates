import re
import unicodedata

def normalizar_texto(texto):
    """Remove acentos e caracteres especiais, deixando apenas letras/números."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9\s]", " ", texto)
    return " ".join(texto.upper().split())


def extrair_cnpj(texto):
    """Extrai o CNPJ no formato 00.000.000/0000-00 e retorna apenas números."""
    if not texto:
        return None
    padrao = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
    match = padrao.search(texto)
    return match.group().replace('.', '').replace('/', '').replace('-', '') if match else None
