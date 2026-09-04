from pathlib import Path
import os
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]
ESCOPO_DRIVE_COMPLETO = "https://www.googleapis.com/auth/drive"
ESCOPO_ARQUIVOS_CRIADOS = "https://www.googleapis.com/auth/drive.file"


class ErroRelatorioDrive(Exception):
    """Erro compreensivel ao publicar um relatorio no Google Drive."""

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


def conectar_google_drive_relatorios(pasta_projeto):
    """Cria um cliente separado, capaz de gravar apenas arquivos do aplicativo."""
    pasta_projeto = Path(pasta_projeto)
    arquivo_credentials = pasta_projeto / "credentials.json"
    arquivo_token = pasta_projeto / "token_drive_relatorios.json"
    escopos = [ESCOPO_ARQUIVOS_CRIADOS]
    credenciais = None

    if arquivo_token.exists():
        credenciais = Credentials.from_authorized_user_file(
            arquivo_token,
            escopos,
        )
        if not credenciais.has_scopes(escopos):
            raise ErroRelatorioDrive(
                "O token de relatorios do Drive nao possui permissao de upload. "
                "Renomeie-o e faca uma nova autorizacao do Google."
            )

    if not credenciais or not credenciais.valid:
        if (
            credenciais
            and credenciais.expired
            and credenciais.refresh_token
        ):
            credenciais.refresh(Request())
        else:
            if not arquivo_credentials.is_file():
                raise ErroRelatorioDrive(
                    "credentials.json nao foi encontrado para autorizar o upload."
                )
            fluxo = InstalledAppFlow.from_client_secrets_file(
                arquivo_credentials,
                escopos,
            )
            credenciais = fluxo.run_local_server(port=0)

        arquivo_token.write_text(
            credenciais.to_json(),
            encoding="utf-8",
        )

    return build("drive", "v3", credentials=credenciais)


def configurar_permissao_relatorio(drive, arquivo_id, modo="restrito", leitor=None):
    """Configura leitura sem tornar o arquivo publico por acidente."""
    modo = str(modo or "restrito").strip().casefold()
    leitor = str(leitor or "").strip()

    if modo == "restrito":
        # O arquivo herda os acessos da pasta onde foi criado.
        return {"modo": "restrito", "herdada_da_pasta": True}

    if modo not in {"usuario", "dominio"}:
        raise ErroRelatorioDrive(
            "Permissao de relatorio invalida. Use restrito, usuario ou dominio."
        )
    if not leitor:
        raise ErroRelatorioDrive(
            "Informe o e-mail ou dominio autorizado a ler os relatorios."
        )

    corpo = {"type": "user" if modo == "usuario" else "domain", "role": "reader"}
    if modo == "usuario":
        corpo["emailAddress"] = leitor
    else:
        corpo["domain"] = leitor

    return drive.permissions().create(
        fileId=arquivo_id,
        body=corpo,
        fields="id,type,role",
        sendNotificationEmail=False,
        supportsAllDrives=True,
    ).execute()


def obter_link_relatorio(arquivo_drive):
    """Retorna o link de visualizacao de um arquivo ja enviado ao Drive."""
    if not isinstance(arquivo_drive, dict) or not arquivo_drive.get("id"):
        raise ErroRelatorioDrive("O Drive nao retornou o ID do relatorio enviado.")
    return arquivo_drive.get("webViewLink") or (
        f"https://drive.google.com/file/d/{arquivo_drive['id']}/view"
    )


def enviar_relatorio_drive(caminho_pdf, pasta_projeto):
    """Envia um PDF e devolve seus metadados; nao altera permissao para publico."""
    caminho_pdf = Path(caminho_pdf)
    if not caminho_pdf.is_file() or caminho_pdf.suffix.casefold() != ".pdf":
        raise ErroRelatorioDrive("O relatorio PDF nao foi encontrado para upload.")

    pasta_id = os.getenv("GOOGLE_DRIVE_PASTA_RELATORIOS_PDF_ID", "").strip()
    if not pasta_id:
        raise ErroRelatorioDrive(
            "GOOGLE_DRIVE_PASTA_RELATORIOS_PDF_ID nao foi configurado."
        )

    drive = conectar_google_drive_relatorios(pasta_projeto)
    midia = MediaFileUpload(
        str(caminho_pdf),
        mimetype="application/pdf",
        resumable=False,
    )
    try:
        arquivo = drive.files().create(
            body={"name": caminho_pdf.name, "parents": [pasta_id]},
            media_body=midia,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
    finally:
        fluxo_arquivo = midia.stream()
        if fluxo_arquivo and not fluxo_arquivo.closed:
            fluxo_arquivo.close()

    modo = os.getenv(
        "GOOGLE_DRIVE_RELATORIOS_PERMISSAO",
        "restrito",
    )
    leitor = os.getenv("GOOGLE_DRIVE_RELATORIOS_LEITOR", "")
    configurar_permissao_relatorio(drive, arquivo["id"], modo, leitor)
    return arquivo


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


def listar_relatorios_json(drive, pasta_id):
    """Lista todos os JSONs da pasta, do mais antigo para o mais recente."""
    pasta_id = str(pasta_id or "").strip()
    if not pasta_id:
        raise ValueError(
            "GOOGLE_DRIVE_PASTA_RELATORIOS_ID não foi configurado no arquivo .env."
        )

    pasta_id_seguro = pasta_id.replace("'", "\\'")
    arquivos = []
    pagina_seguinte = None
    while True:
        resultado = drive.files().list(
            q=(
                f"'{pasta_id_seguro}' in parents and trashed = false and "
                "(mimeType = 'application/json' or name contains '.json')"
            ),
            pageSize=1000,
            pageToken=pagina_seguinte,
            orderBy="modifiedTime asc",
            fields="nextPageToken, files(id, name, modifiedTime, mimeType)",
            spaces="drive",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        arquivos.extend(resultado.get("files", []))
        pagina_seguinte = resultado.get("nextPageToken")
        if not pagina_seguinte:
            break

    return sorted(
        arquivos,
        key=lambda arquivo: (
            arquivo.get("modifiedTime", ""),
            arquivo.get("id", ""),
        ),
    )


def ler_relatorio_json(drive, arquivo):
    """Baixa e decodifica um JSON descrito pela API do Drive."""
    if not isinstance(arquivo, dict) or not arquivo.get("id"):
        raise ValueError("Metadados inválidos para o arquivo JSON do Drive.")
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


def ler_relatorio_json_mais_recente(drive, pasta_id):
    """Baixa e decodifica o JSON mais recentemente alterado de uma pasta."""
    arquivos = listar_relatorios_json(drive, pasta_id)
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo JSON foi encontrado na pasta do Drive.")
    return ler_relatorio_json(drive, arquivos[-1])
