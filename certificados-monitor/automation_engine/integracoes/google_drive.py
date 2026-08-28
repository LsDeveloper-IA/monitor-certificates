from pathlib import Path
import os
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]
ESCOPO_DRIVE_COMPLETO = "https://www.googleapis.com/auth/drive"

def conectar_google_drive(pasta_projeto):
    pasta_projeto = Path(pasta_projeto)
    arquivo_credentials = pasta_projeto / "credentials.json"
    arquivo_token = pasta_projeto / "token.json"
    credenciais = None

    if arquivo_token.exists():
        # Não substitui os escopos salvos no token. Um token legado pode ter o
        # escopo completo do Drive, que já inclui leitura; forçar "readonly"
        # durante a renovação faz o Google responder com invalid_scope.
        credenciais = Credentials.from_authorized_user_file(
            arquivo_token,
        )
        escopos_concedidos = set(credenciais.scopes or [])
        if not escopos_concedidos.intersection({SCOPES[0], ESCOPO_DRIVE_COMPLETO}):
            raise ValueError(
                "O token do Google não possui permissão de leitura do Drive."
            )

    if not credenciais or not credenciais.valid:
        if (
            credenciais
            and credenciais.expired
            and credenciais.refresh_token
        ):
            credenciais.refresh(Request())
        else:
            fluxo = InstalledAppFlow.from_client_secrets_file(
                arquivo_credentials,
                SCOPES,
            )
            credenciais = fluxo.run_local_server(port=0)

        arquivo_token.write_text(
            credenciais.to_json(),
            encoding="utf-8",
        )

    return build("drive", "v3", credentials=credenciais)


def listar_arquivos(drive, consulta):
    arquivos = []
    pagina_seguinte = None

    while True:
        resultado = drive.files().list(
            q=consulta,
            pageSize=1000,
            pageToken=pagina_seguinte,
            fields="nextPageToken, files(id, name, mimeType, parents)",
            spaces="drive",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        arquivos.extend(resultado.get("files", []))
        pagina_seguinte = resultado.get("nextPageToken")

        if not pagina_seguinte:
            return arquivos


def buscar_documentos_de_senha(drive):
    pasta_e_cnpj_id = os.getenv("GOOGLE_DRIVE_PASTA_E_CNPJ_ID", "").strip()
    if not pasta_e_cnpj_id:
        raise ValueError(
            "GOOGLE_DRIVE_PASTA_E_CNPJ_ID não foi configurado no arquivo .env."
        )
    consulta_pastas = (
        f"'{pasta_e_cnpj_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )
    pastas_empresas = listar_arquivos(drive, consulta_pastas)
    pastas_por_id = {
        pasta["id"]: pasta["name"]
        for pasta in pastas_empresas
    }

    consulta_documentos = (
        "mimeType = 'application/vnd.google-apps.document' and "
        "trashed = false"
    )
    documentos = listar_arquivos(drive, consulta_documentos)
    documentos_por_pasta = {}

    for documento in documentos:
        for pasta_pai_id in documento.get("parents", []):
            if pasta_pai_id in pastas_por_id:
                documentos_por_pasta.setdefault(pasta_pai_id, []).append(
                    documento
                )
                break

    documentos_por_empresa = {}

    for pasta_id, documentos_da_pasta in documentos_por_pasta.items():
        documentos_chamados_senha = [
            documento
            for documento in documentos_da_pasta
            if documento["name"].strip().casefold().startswith("senha")
        ]

        if documentos_chamados_senha:
            documento_escolhido = documentos_chamados_senha[0]
        elif len(documentos_da_pasta) == 1:
            # Algumas empresas usam a própria senha como nome do documento.
            documento_escolhido = documentos_da_pasta[0]
        else:
            # Com vários documentos, não escolhemos um aleatoriamente.
            continue

        nome_empresa = pastas_por_id[pasta_id]
        documentos_por_empresa[nome_empresa.strip().casefold()] = {
            "id": documento_escolhido["id"],
            "empresa": nome_empresa,
        }

    return documentos_por_empresa


def ler_senha_google_docs(drive, documento_id):
    conteudo_em_bytes = drive.files().export(
        fileId=documento_id,
        mimeType="text/plain",
    ).execute()

    return conteudo_em_bytes.decode("utf-8-sig").rstrip("\r\n")


def ler_relatorio_json_mais_recente(drive, pasta_id):
    """Baixa e decodifica o JSON mais recentemente alterado de uma pasta."""
    pasta_id = str(pasta_id or "").strip()
    if not pasta_id:
        raise ValueError(
            "GOOGLE_DRIVE_PASTA_RELATORIOS_ID não foi configurado no arquivo .env."
        )

    pasta_id_seguro = pasta_id.replace("'", "\\'")
    resultado = drive.files().list(
        q=(
            f"'{pasta_id_seguro}' in parents and trashed = false and "
            "(mimeType = 'application/json' or name contains '.json')"
        ),
        pageSize=100,
        orderBy="modifiedTime desc",
        fields="files(id, name, modifiedTime, mimeType)",
        spaces="drive",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    arquivos = resultado.get("files", [])
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo JSON foi encontrado na pasta do Drive.")

    arquivo = arquivos[0]
    conteudo = drive.files().get_media(
        fileId=arquivo["id"], supportsAllDrives=True
    ).execute()
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("utf-8-sig")

    dados = json.loads(conteudo)
    if not isinstance(dados, dict):
        raise ValueError("O relatório JSON precisa conter um objeto na raiz.")
    dados["arquivo_drive"] = {
        "id": arquivo["id"],
        "nome": arquivo["name"],
        "modificado_em": arquivo.get("modifiedTime"),
    }
    return dados
