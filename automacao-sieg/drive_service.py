import _bootstrap
from config import PASTA_EXECUCAO, SCOPES, SIMILARIDADE_MINIMA_PASTA
from sieg_comum import drive as cliente
from sieg_comum.drive import (
    criar_indice_pastas_drive,
    listar_pastas_no_drive, baixar_arquivo_drive, exportar_google_doc,
    limpar_senha_certificado,
)


def autenticar_drive():
    return cliente.autenticar_drive(
        PASTA_EXECUCAO / "credentials.json", PASTA_EXECUCAO / "token.json", SCOPES,
    )


def iterar_certificados_candidatos_drive(nome_empresa, service, root_folder_id,
                                       indice_pastas=None, limiar=SIMILARIDADE_MINIMA_PASTA):
    return cliente.iterar_certificados_candidatos_drive(
        nome_empresa, service, root_folder_id, indice_pastas, limiar,
    )
