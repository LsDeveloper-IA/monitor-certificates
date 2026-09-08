import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PASTA_PROJETO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_PROJETO / "automation_engine"))
load_dotenv(PASTA_PROJETO / ".env", override=True)

from resumo_atualizacoes_email import enviar_resumo_atualizacoes


def main():
    destinatario = os.getenv("EMAIL_RESUMO_ATUALIZACOES", "").strip()
    if not destinatario:
        raise SystemExit(
            "Configure EMAIL_RESUMO_ATUALIZACOES no arquivo .env antes do teste."
        )

    resumo_ficticio = {
        "alteracoes_certificados": [
            {
                "tipo": "vencimento_alterado",
                "empresa": "EMPRESA FICTICIA - TESTE DE EMAIL",
                "cnpj": "00000000000100",
                "arquivo_anterior": "certificado_teste_anterior.pfx",
                "arquivo_novo": "certificado_teste_novo.pfx",
                "vencimento_anterior": "2026-09-08",
                "vencimento_novo": "2027-09-08",
            }
        ]
    }

    print("Enviando resumo ficticio para o e-mail interno configurado...")
    resultado = enviar_resumo_atualizacoes(resumo_ficticio)
    status = resultado.get("status")

    if status == "enviado":
        print("Teste concluido: o Gmail aceitou o resumo de atualizacoes.")
        print(f"Message-ID: {resultado.get('message_id')}")
        return

    if status == "desativado":
        raise SystemExit(
            "Envio desativado. Defina "
            "ENVIAR_RESUMO_ATUALIZACOES_AUTOMATICO=sim no .env."
        )

    if status == "falhou":
        raise SystemExit(f"Falha no envio: {resultado.get('erro')}")

    raise SystemExit(f"Teste nao enviado. Status: {status}")


if __name__ == "__main__":
    main()
