import io
import hashlib
import re
from difflib import SequenceMatcher

from docx import Document
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from .identidade import extrair_cnpj, normalizar_texto
from .certificados import verificar_validade_certificado_bytes

MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
SIMILARIDADE_MINIMA_PASTA = 0.85


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

def autenticar_drive(credentials_path, token_path, scopes):
    """Autentica no Drive usando exclusivamente credenciais OAuth em JSON."""
    credentials_path, token_path = Path(credentials_path), Path(token_path)
    if token_path.name.lower() != "token.json":
        raise ValueError("O token OAuth deve usar o nome e formato token.json.")
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if not creds.has_scopes(scopes):
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None
        if not creds or not creds.valid:
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credenciais do Google nao encontradas: {credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds)


def listar_pastas_no_drive(service, parent_id):
    return listar_itens_drive(service, parent_id, "application/vnd.google-apps.folder")


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
        "cache_certificados_por_pasta": {},
        "total": len(pastas),
    }


def _buscar_certificados_indexados(pasta, service, indice):
    """Retorna todas as combinações válidas da pasta, consultando-a uma vez."""
    pasta_id = pasta["id"]
    cache = indice.setdefault("cache_certificados_por_pasta", {})
    if pasta_id not in cache:
        certificados = _extrair_certificados_da_pasta_drive(pasta_id, service)
        cache[pasta_id] = certificados
    return cache[pasta_id]


def _baixar_requisicao(request):
    """Consome downloads e exportações usando o mesmo transporte."""
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh


def baixar_arquivo_drive(service, file_id):
    """Baixa um arquivo do Drive e retorna um BytesIO."""
    return _baixar_requisicao(service.files().get_media(fileId=file_id))


def exportar_google_doc(service, file_id):
    """Exporta um Google Docs nativo como texto."""
    request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    return _baixar_requisicao(request).read().decode("utf-8-sig", errors="ignore").strip()


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


def _ordenar_pastas_por_similaridade(nome_empresa, indice, limiar, *, modo="similaridade"):
    """Ordena pastas exatas/equivalentes e aproximações acima do limiar."""
    nome_normalizado = normalizar_texto(nome_empresa) if nome_empresa else ""
    if not nome_normalizado:
        return []

    if modo == "contido":
        pastas = [{"pasta": pasta, "nome": nome} for nome, pasta in indice["por_nome"]
                  if nome and (nome_normalizado in nome or nome in nome_normalizado)]
        return sorted(pastas, key=lambda item: (item["nome"] != nome_normalizado, len(item["nome"])))

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


def _extrair_certificados_da_pasta_drive(pasta_id, service):
    """Retorna todas as combinações PFX/senha válidas de uma pasta."""
    arquivos = listar_itens_drive(service, pasta_id)

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
            senha = ler_senha_drive(service, f_senha)

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


def listar_itens_drive(servico_drive, id_pasta, mime_type=None):
    """Lista itens diretamente dentro de uma pasta do Google Drive."""
    consulta = f"'{id_pasta}' in parents and trashed = false"
    if mime_type:
        consulta += f" and mimeType = '{mime_type}'"

    itens = []
    pagina = None
    while True:
        resposta = servico_drive.files().list(
            q=consulta,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=pagina,
            pageSize=1000,
        ).execute()
        itens.extend(resposta.get("files", []))
        pagina = resposta.get("nextPageToken")
        if not pagina:
            return itens


def buscar_arquivos_por_nome_empresa(nome_empresa_alvo, servico_drive, id_pasta_raiz, diretorio):
    """Busca a pasta da empresa no Drive e baixa o .pfx e a senha."""
    indice = criar_indice_pastas_drive(servico_drive, id_pasta_raiz)
    pastas_candidatas = [item["pasta"] for item in
                        _ordenar_pastas_por_similaridade(nome_empresa_alvo, indice, 1.0, modo="contido")]

    for pasta_empresa in pastas_candidatas:
        print(f"  Verificando pasta no Drive: {pasta_empresa['name']}")
        arquivos = listar_itens_drive(servico_drive, pasta_empresa["id"])
        arquivos_pfx = [
            f for f in arquivos if f["name"].lower().endswith((".pfx", ".p12"))
        ]
        arquivos_senha = [
            f for f in arquivos
            if f.get("mimeType") == "application/vnd.google-apps.document"
            or f["name"].lower().endswith((".txt", ".docx", ".doc"))
        ]

        if not arquivos_pfx:
            print("    Nenhum arquivo .pfx/.p12 encontrado nessa pasta.")
            continue
        if not arquivos_senha:
            print("    Nenhum arquivo de senha encontrado nessa pasta.")
            continue

        caminho_pfx = str(baixar_arquivo_para_disco(servico_drive, arquivos_pfx[0], diretorio))
        arquivo_senha = arquivos_senha[0]
        try:
            senha = ler_senha_drive(servico_drive, arquivo_senha)
        except Exception as erro:
            print(f"Não foi possível ler {arquivo_senha['name']}: {erro}")
            continue

        if senha:
            return caminho_pfx, senha
        print(f"    Arquivo de senha vazio ou ilegivel: {arquivo_senha['name']}")

    return None, None


def ler_senha_drive(service, arquivo):
    """Le TXT, DOCX/DOC ou Google Docs e normaliza a senha em um unico lugar."""
    if arquivo.get("mimeType") == MIME_GOOGLE_DOC:
        senha = exportar_google_doc(service, arquivo["id"])
    else:
        conteudo = baixar_arquivo_drive(service, arquivo["id"])
        if arquivo["name"].lower().endswith(".txt"):
            senha = conteudo.read().decode("utf-8-sig", errors="ignore")
        elif arquivo["name"].lower().endswith((".docx", ".doc")):
            senha = " ".join(p.text.strip() for p in Document(conteudo).paragraphs if p.text.strip())
        else:
            return None
    return limpar_senha_certificado(senha)


def baixar_arquivo_para_disco(service, arquivo, diretorio):
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    destino = diretorio / f"{arquivo['id']}_{Path(arquivo['name']).name}"
    destino.write_bytes(baixar_arquivo_drive(service, arquivo["id"]).read())
    return destino
