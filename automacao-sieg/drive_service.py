import io
import hashlib
import pickle
import re
from difflib import SequenceMatcher

from docx import Document
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import (
    MIME_GOOGLE_DOC,
    PASTA_EXECUCAO,
    SCOPES,
    SIMILARIDADE_MINIMA_PASTA,
)
from utilitarios import extrair_cnpj, normalizar_texto, verificar_validade_certificado_bytes


def limpar_senha_certificado(senha):
    if not senha:
        return None

    senha = senha.replace("\ufeff", "")
    senha = senha.replace("\u200b", "")
    senha = senha.replace("\xa0", " ")
    senha = senha.strip()

    senha = re.sub(
        r"^senha\s*:\s*",
        "",
        senha,
        flags=re.IGNORECASE,
    )

    return senha.strip()

def autenticar_drive():
    """Autentica e retorna o serviço da API do Google Drive."""
    creds = None
    token_path = PASTA_EXECUCAO / "token.pickle"
    credentials_path = PASTA_EXECUCAO / "credentials.json"
    if token_path.exists():
        with token_path.open('rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Arquivo do Google Drive não encontrado: {credentials_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with token_path.open('wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)


def listar_pastas_no_drive(service, parent_id):
    """Lista todas as pastas dentro de uma pasta do Drive."""
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    pastas = []
    page_token = None
    while True:
        results = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        pastas.extend(results.get('files', []))
        page_token = results.get('nextPageToken')
        if not page_token:
            return pastas


def criar_indice_pastas_drive(service, root_folder_id):
    """Lista a pasta raiz uma única vez e cria índices por CNPJ e por nome."""
    pastas = listar_pastas_no_drive(service, root_folder_id)
    indice_cnpj = {}
    indice_nome = []

    for pasta in pastas:
        nome_pasta = pasta.get('name', '')
        cnpj_pasta = extrair_cnpj(nome_pasta)
        if cnpj_pasta:
            indice_cnpj.setdefault(cnpj_pasta, pasta)
        indice_nome.append((normalizar_texto(nome_pasta), pasta))

    return {
        "por_cnpj": indice_cnpj,
        "por_nome": indice_nome,
        "cache_certificados": {},
        "cache_certificados_por_pasta": {},
        "total": len(pastas),
    }


def _buscar_certificado_indexado(pasta, service, indice):
    """Consulta cada pasta encontrada no máximo uma vez durante a execução."""
    pasta_id = pasta['id']
    cache = indice.setdefault("cache_certificados", {})
    if pasta_id not in cache:
        cache[pasta_id] = _extrair_certificado_da_pasta_drive(pasta_id, service)
    return cache[pasta_id]


def _buscar_certificados_indexados(pasta, service, indice):
    """Retorna todas as combinações válidas da pasta, consultando-a uma vez."""
    pasta_id = pasta["id"]
    cache = indice.setdefault("cache_certificados_por_pasta", {})
    if pasta_id not in cache:
        certificados = _extrair_certificados_da_pasta_drive(pasta_id, service)
        cache[pasta_id] = certificados
    return cache[pasta_id]


def baixar_arquivo_drive(service, file_id):
    """Baixa um arquivo do Drive e retorna um BytesIO."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh


def exportar_google_doc(service, file_id):
    """Exporta um Google Docs nativo como texto."""
    request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue().decode("utf-8", errors="ignore").strip()


def _nomes_formam_abreviacao_ancorada(nome_a, nome_b):
    """Aceita abreviação quando um nome é um prefixo distintivo do outro."""
    termos_a = nome_a.split()
    termos_b = nome_b.split()
    termos_curto, termos_longo = sorted(
        (termos_a, termos_b), key=len
    )
    if len(termos_curto) < 2:
        return False
    if termos_longo[:len(termos_curto)] != termos_curto:
        return False

    # Evita considerar prefixos genéricos muito curtos como identidade.
    ancora = "".join(termos_curto[:2])
    return len(ancora) >= 10


def _ordenar_pastas_por_similaridade(nome_empresa, indice, limiar):
    """Ordena pastas exatas/equivalentes e aproximações acima do limiar."""
    nome_normalizado = normalizar_texto(nome_empresa) if nome_empresa else ""
    if not nome_normalizado:
        return []

    nome_compacto = nome_normalizado.replace(" ", "")
    candidatos_por_id = {}

    for nome_pasta_normalizado, pasta in indice["por_nome"]:
        pasta_id = pasta["id"]
        nome_pasta_compacto = nome_pasta_normalizado.replace(" ", "")

        if nome_normalizado == nome_pasta_normalizado:
            prioridade = 0
            similaridade = 1.0
            tipo = "nome exato"
        elif nome_compacto == nome_pasta_compacto:
            prioridade = 1
            similaridade = 1.0
            tipo = "nome equivalente"
        elif _nomes_formam_abreviacao_ancorada(
            nome_normalizado, nome_pasta_normalizado
        ):
            prioridade = 1
            similaridade = 1.0
            tipo = "nome abreviado ancorado"
        else:
            similaridade = max(
                SequenceMatcher(
                    None, nome_normalizado, nome_pasta_normalizado
                ).ratio(),
                SequenceMatcher(
                    None, nome_compacto, nome_pasta_compacto
                ).ratio(),
            )
            if similaridade < limiar:
                continue
            prioridade = 2
            tipo = "nome semelhante"

        candidato = {
            "pasta": pasta,
            "prioridade": prioridade,
            "similaridade": similaridade,
            "tipo_correspondencia": tipo,
            "nome_normalizado": nome_pasta_normalizado,
        }
        anterior = candidatos_por_id.get(pasta_id)
        if anterior is None or (
            prioridade, -similaridade
        ) < (
            anterior["prioridade"], -anterior["similaridade"]
        ):
            candidatos_por_id[pasta_id] = candidato

    candidatos = list(candidatos_por_id.values())
    if any(
        candidato["similaridade"] == 1.0
        for candidato in candidatos
    ):
        candidatos = [
            candidato
            for candidato in candidatos
            if candidato["similaridade"] == 1.0
        ]

    return sorted(
        candidatos,
        key=lambda candidato: (
            candidato["prioridade"],
            -candidato["similaridade"],
            candidato["nome_normalizado"],
            candidato["pasta"]["id"],
        ),
    )


def iterar_certificados_candidatos_drive(
    nome_empresa,
    service,
    root_folder_id,
    indice_pastas=None,
    limiar=SIMILARIDADE_MINIMA_PASTA,
):
    """Produz certificados de pastas com nome altamente compatível."""
    indice = (
        indice_pastas
        if indice_pastas is not None
        else criar_indice_pastas_drive(service, root_folder_id)
    )

    pastas = _ordenar_pastas_por_similaridade(nome_empresa, indice, limiar)
    if pastas:
        print(
            f"  📁 {len(pastas)} pasta(s) candidata(s) com "
            f"similaridade mínima de {limiar:.0%}"
        )

    hashes_emitidos = set()
    for candidato_pasta in pastas:
        pasta = candidato_pasta["pasta"]
        print(
            f"  📂 Verificando {pasta['name']} "
            f"({candidato_pasta['similaridade']:.1%})"
        )
        certificados = _buscar_certificados_indexados(pasta, service, indice)
        for certificado in certificados:
            hash_pfx = hashlib.sha256(certificado["pfx_bytes"]).digest()
            if hash_pfx in hashes_emitidos:
                continue
            hashes_emitidos.add(hash_pfx)
            yield {
                **certificado,
                "pasta_id": pasta["id"],
                "pasta_nome": pasta["name"],
                "similaridade": candidato_pasta["similaridade"],
                "tipo_correspondencia": candidato_pasta[
                    "tipo_correspondencia"
                ],
            }


def buscar_certificado_por_cnpj_drive(
    cnpj, nome_empresa, service, root_folder_id, indice_pastas=None
):
    """Compatibilidade: retorna o primeiro candidato encontrado pelo nome."""
    del cnpj
    primeiro = next(
        iterar_certificados_candidatos_drive(
            nome_empresa,
            service,
            root_folder_id,
            indice_pastas,
        ),
        None,
    )
    if primeiro is None:
        return None, None
    return primeiro["pfx_bytes"], primeiro["senha"]


def _extrair_certificados_da_pasta_drive(pasta_id, service):
    """Retorna todas as combinações PFX/senha válidas de uma pasta."""
    query = f"'{pasta_id}' in parents and trashed=false"
    arquivos = []
    page_token = None
    while True:
        results = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        arquivos.extend(results.get('files', []))
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    
    arquivos_pfx = sorted(
        (
            f
            for f in arquivos
            if f['name'].lower().endswith(('.pfx', '.p12'))
        ),
        key=lambda arquivo: (arquivo["name"].lower(), arquivo["id"]),
    )
    arquivos_senha = [
        f for f in arquivos
        if f.get('mimeType') == MIME_GOOGLE_DOC
        or f['name'].lower().endswith(('.txt', '.docx', '.doc'))
    ]
    
    if not arquivos_pfx or not arquivos_senha:
        return []
    
    # Lê todas as senhas candidatas. Pastas antigas podem conter mais de um
    # certificado e mais de um documento de senha.
    senhas = []
    for f_senha in arquivos_senha:
        try:
            senha = None
            if f_senha.get("mimeType") == MIME_GOOGLE_DOC:
                senha = exportar_google_doc(service, f_senha["id"])
                conteudo = None
            else:
                conteudo = baixar_arquivo_drive(service, f_senha["id"])

            if f_senha["name"].lower().endswith(".txt") and conteudo:
                senha = conteudo.read().decode(
                    "utf-8-sig",
                    errors="ignore"
                ).strip()

            elif f_senha["name"].lower().endswith((".docx", ".doc")) and conteudo:
                doc = Document(conteudo)
                senha = " ".join(
                    p.text.strip()
                    for p in doc.paragraphs
                    if p.text.strip()
                )

            senha = limpar_senha_certificado(senha)

            if senha and senha not in senhas:
                senhas.append(senha)
        except Exception as erro:
            print(
                f"  ⚠️ Não foi possível ler o arquivo de senha "
                f"{f_senha['name']}: {erro}"
            )

    if not senhas:
        print("  ⚠️ Nenhuma senha legível foi encontrada na pasta.")
        return []

    certificados = []
    hashes_pfx = set()
    # Testa cada combinação, pois arquivos antigos podem continuar na pasta.
    for f_pfx in arquivos_pfx:
        try:
            pfx_bytes = baixar_arquivo_drive(service, f_pfx["id"]).read()
            print(f"  🔎 Arquivo testado: {f_pfx['name']} ({len(pfx_bytes)} bytes)")
            for numero_senha, senha in enumerate(senhas, start=1):
                print(f"  🔐 Testando senha candidata {numero_senha}/{len(senhas)}")
                if verificar_validade_certificado_bytes(pfx_bytes, senha):
                    hash_pfx = hashlib.sha256(pfx_bytes).digest()
                    if hash_pfx not in hashes_pfx:
                        hashes_pfx.add(hash_pfx)
                        certificados.append({
                            "pfx_bytes": pfx_bytes,
                            "senha": senha,
                            "arquivo_id": f_pfx["id"],
                            "arquivo_nome": f_pfx["name"],
                        })
                    break
        except Exception as erro:
            print(f"  ⚠️ Erro ao processar {f_pfx['name']}: {erro}")

    if not certificados:
        print("  ⚠️ Nenhuma combinação de certificado e senha da pasta é válida.")
    return certificados


def _extrair_certificado_da_pasta_drive(pasta_id, service):
    """Compatibilidade: retorna a primeira combinação válida de uma pasta."""
    certificados = _extrair_certificados_da_pasta_drive(pasta_id, service)
    if not certificados:
        return None, None
    primeiro = certificados[0]
    return primeiro["pfx_bytes"], primeiro["senha"]
