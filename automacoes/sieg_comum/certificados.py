from datetime import datetime, timezone
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import pkcs12

def verificar_validade_certificado_bytes(pfx_bytes, senha):
    """Verifica se o certificado (em bytes) é válido."""
    try:
        senha_bytes = senha.strip().encode('utf-8') if senha else None
        _, cert, _ = pkcs12.load_key_and_certificates(pfx_bytes, senha_bytes, backend=default_backend())
        if not cert:
            return False
        if hasattr(cert, "not_valid_after_utc"):
            data_validade = cert.not_valid_after_utc
            agora = datetime.now(timezone.utc)
        else:
            data_validade = cert.not_valid_after
            agora = datetime.now()
        if agora > data_validade:
            print(f"  ⛔ Certificado vencido em {data_validade.strftime('%d/%m/%Y')}")
            return False
        print(f"  🟢 Certificado válido até {data_validade.strftime('%d/%m/%Y')}")
        return True
    except Exception as e:
        print(f"  ⚠️ Erro ao validar certificado: {e}")
        return False
