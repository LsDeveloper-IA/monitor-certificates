import time
import traceback

from automacao import executar_automacao_sieg
from config import ESPERA_ENTRE_TENTATIVAS, MAX_TENTATIVAS_EXECUCAO


def executar_com_retentativas():
    """Repete a execução completa quando ocorre um erro não tratado."""
    for tentativa in range(1, MAX_TENTATIVAS_EXECUCAO + 1):
        try:
            print(f"\n[Execucao] tentativa {tentativa}/{MAX_TENTATIVAS_EXECUCAO}")
            executar_automacao_sieg()
            return True
        except KeyboardInterrupt:
            print("\n[Interrompida] execucao interrompida manualmente.")
            return False
        except Exception as erro:
            print(f"\n[Falha critica] execucao {tentativa}: {erro}")
            traceback.print_exc()
            if tentativa == MAX_TENTATIVAS_EXECUCAO:
                print("[Limite] limite de tentativas atingido.")
                return False
            espera = ESPERA_ENTRE_TENTATIVAS * tentativa
            print(f"[Retry] nova tentativa em {espera} segundos...")
            time.sleep(espera)


if __name__ == "__main__":
    executar_com_retentativas()

