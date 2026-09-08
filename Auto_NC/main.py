import os
import json
import re
import tempfile
import time
import unicodedata
from pathlib import Path
from datetime import datetime
from docx import Document
from playwright.sync_api import sync_playwright, expect
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


def carregar_arquivo_env():
    """Carrega variáveis .env sem substituir valores já definidos no ambiente."""
    arquivo_env = Path(__file__).with_name(".env")
    if not arquivo_env.exists():
        return

    for linha in arquivo_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        linha = linha.removeprefix("$env:")
        nome, separador, valor = linha.partition("=")
        if separador:
            os.environ.setdefault(nome.strip(), valor.strip().strip('"\''))


carregar_arquivo_env()

# ---------------------------------------------------------
# CONFIGURAÇÕES DE PASTA E TEMPOS DE ESPERA
# ---------------------------------------------------------
# Configure o ID da pasta raiz no Google Drive e coloque credentials.json neste diretório.
ID_PASTA_DRIVE_CERTIFICADOS = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
ARQUIVO_CREDENCIAIS_GOOGLE = Path(
    os.getenv("GOOGLE_DRIVE_CREDENTIALS", "credentials.json")
)
ARQUIVO_TOKEN_GOOGLE = Path(
    os.getenv("GOOGLE_DRIVE_TOKEN", "token.json")
)
ESCOPO_GOOGLE_DRIVE = ["https://www.googleapis.com/auth/drive"]
ID_PASTA_DRIVE_RELATORIO = os.getenv(
    "AUTO_NC_REPORT_FOLDER_ID", "1meQotNC34O7gVYUGFGcK2p_qeT5r9eX4"
)
PASTA_TEMPORARIA_DRIVE = Path(tempfile.gettempdir()) / "auto_nc_drive"
ARQUIVO_RELATORIO_SEM_CERTIFICADO = Path(
    os.getenv(
        "AUTO_NC_RELATORIO_PATH",
        str(Path(__file__).with_name("empresas_sem_certificado.json")),
    )
)
SIEG_EMAIL = os.getenv("SIEG_EMAIL", "")
SIEG_SENHA = os.getenv("SIEG_SENHA", "")

# Tempos de espera (em segundos)
TIME_CURTO = 2.5   # Pausa entre as etapas principais
PAUSA_CADA_ACAO_MS = 600  # Espera automatica apos cada acao do Playwright
TIME_LONGO = 6.0   # Pausa para validação do PFX (TIMEEEEE)
TIME_FINAL = 15.0  # Pausa após "Confirmar e finalizar"


# ---------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------
def normalizar_texto(texto):
    """Remove acentos, caracteres especiais e converte para maiúsculas."""
    if not texto:
        return ""
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    texto_sem_acento = "".join([c for c in texto_nfkd if not unicodedata.combining(c)])
    texto_maiusculo = texto_sem_acento.upper()
    texto_limpo = re.sub(r"[^A-Z0-9\s]", " ", texto_maiusculo)
    return " ".join(texto_limpo.split())


def salvar_empresas_sem_certificado(empresas, servico_drive=None):
    """Disponibiliza no painel a lista parcial da execução atual."""
    unicas = {normalizar_texto(item["nome"]): item for item in empresas}
    conteudo = {
        "atualizado_em": datetime.now().isoformat(),
        "empresas": sorted(unicas.values(), key=lambda item: item["nome"]),
    }
    ARQUIVO_RELATORIO_SEM_CERTIFICADO.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_RELATORIO_SEM_CERTIFICADO.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporario, ARQUIVO_RELATORIO_SEM_CERTIFICADO)
    if servico_drive is not None:
        enviar_relatorio_para_drive(servico_drive)


def enviar_relatorio_para_drive(servico_drive):
    """Cria ou atualiza o resumo final na pasta configurada do Drive."""
    nome_arquivo = ARQUIVO_RELATORIO_SEM_CERTIFICADO.name
    resposta = servico_drive.files().list(
        q=(
            f"'{ID_PASTA_DRIVE_RELATORIO}' in parents and "
            f"name = '{nome_arquivo}' and trashed = false"
        ),
        spaces="drive",
        fields="files(id, name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    midia = MediaFileUpload(
        str(ARQUIVO_RELATORIO_SEM_CERTIFICADO),
        mimetype="application/json",
        resumable=False,
    )
    arquivos = resposta.get("files", [])
    if arquivos:
        arquivo = servico_drive.files().update(
            fileId=arquivos[0]["id"],
            media_body=midia,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        acao = "atualizado"
    else:
        arquivo = servico_drive.files().create(
            body={"name": nome_arquivo, "parents": [ID_PASTA_DRIVE_RELATORIO]},
            media_body=midia,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        acao = "criado"
    print(
        f"Resumo final {acao} no Google Drive: {arquivo.get('name')} "
        f"(ID: {arquivo.get('id')})"
    )


def extrair_id_pasta_drive(valor):
    """Aceita tanto o ID puro quanto uma URL de pasta do Google Drive."""
    correspondencia = re.search(r"/folders/([^/?]+)", valor)
    if correspondencia:
        return correspondencia.group(1)
    return valor.split("?", 1)[0].split("#", 1)[0].strip().rstrip("/").split("/")[-1]


def clicar_com_rolagem(page, texto_ou_seletor, tentativas_max=5, pixels_scroll=350):
    """Procura por um elemento. Se não encontrar, rola a tela e tenta novamente."""
    for i in range(tentativas_max):
        try:
            if not texto_ou_seletor.startswith(".") and not texto_ou_seletor.startswith("#") and not texto_ou_seletor.startswith("input") and not texto_ou_seletor.startswith("//"):
                elemento = page.get_by_text(re.compile(re.escape(texto_ou_seletor), re.IGNORECASE)).first
            else:
                elemento = page.locator(texto_ou_seletor).first

            if elemento.is_visible():
                elemento.scroll_into_view_if_needed()
                elemento.click()
                print(f"  └─ Elemento '{texto_ou_seletor}' localizado e clicado.")
                return True
        except Exception:
            pass

        print(f"  └─ '{texto_ou_seletor}' não visível. Rolando tela ({i+1}/{tentativas_max})...")
        page.evaluate(f"window.scrollBy(0, {pixels_scroll})")
        time.sleep(1.0)

    print(f"❌ Não foi possível encontrar/clicar em '{texto_ou_seletor}'.")
    return False


def clicar_editar_cadastro(page):
    """Clica no item aberto pelo menu de tres pontos, inclusive via Vue Teleport."""
    seletores = [
        "li:has-text('Editar cadastro')",
        "[role='menuitem']:has-text('Editar cadastro')",
        "label:has-text('Editar cadastro')",
        "xpath=//*[@id='app']/main/section/div/section/section[2]/div[1]/section/div[4]/div[2]/div/div[1]/table/tbody/tr[4]/td[8]/teleport/ul/li[2]",
    ]

    for seletor in seletores:
        item = page.locator(seletor).filter(has_text=re.compile(
            r"Editar\s+cadastro", re.IGNORECASE
        )).last
        try:
            item.wait_for(state="visible", timeout=800)
            item.click()
            print("  └─ 'Editar cadastro' localizado e clicado.")
            return
        except Exception:
            continue

    raise RuntimeError(
        "O menu de opcoes abriu, mas o item 'Editar cadastro' nao ficou visivel."
    )


def abrir_edicao_empresa(page, linha):
    """Abre a edicao reproduzindo o fluxo funcional do projeto preservado."""
    print("  Abrindo edicao da empresa...")
    titulo_edicao = page.get_by_text("Editar CNPJ/CPF", exact=True)

    try:
        print("  Tentando clique duplo na linha...")
        linha.scroll_into_view_if_needed()
        linha.dblclick()
        titulo_edicao.wait_for(state="visible", timeout=5000)
        print("  Edicao aberta via clique duplo.")
        return True
    except Exception as err:
        if titulo_edicao.count() and titulo_edicao.last.is_visible():
            print("  Edicao aberta via clique duplo.")
            return True
        print(f"  Clique duplo nao abriu a edicao: {err}")

    try:
        print("  Tentando abrir o menu de opcoes...")
        botoes = linha.locator("td:last-child button")
        btn_opcoes = None
        for indice in range(botoes.count()):
            candidato = botoes.nth(indice)
            if candidato.is_visible():
                btn_opcoes = candidato
                break

        if btn_opcoes is None:
            raise RuntimeError("botao de opcoes da linha nao encontrado")

        btn_opcoes.scroll_into_view_if_needed()
        btn_opcoes.click()
        print("  Menu de opcoes aberto.")

        itens_editar = page.get_by_text("Editar cadastro", exact=True)
        item_visivel = None
        for indice in range(itens_editar.count()):
            candidato = itens_editar.nth(indice)
            if candidato.is_visible():
                item_visivel = candidato
                break

        if item_visivel is None:
            raise RuntimeError("opcao 'Editar cadastro' nao encontrada no menu")

        item_visivel.click()
        titulo_edicao.last.wait_for(state="visible", timeout=10000)
        print("  'Editar cadastro' aberto.")
        return True
    except Exception as err:
        print(f"  Erro ao abrir edicao pelo menu: {err}")
        return False


def preencher_uf_se_necessario(page):
    """Preenche a UF com CE somente quando o campo estiver vazio."""
    seletores = (
        "select[name*='uf' i], select[id*='uf' i], "
        "input[name*='uf' i], input[id*='uf' i], "
        "[role='combobox'][name*='uf' i], [role='combobox'][id*='uf' i], "
        "input[placeholder*='UF' i], [aria-label*='UF' i]"
    )
    campo_uf = None

    # A tela pode montar o formulario alguns segundos depois de abrir a edicao.
    xpath_label_estado = (
        "xpath=/html/body/div[5]/div/div[2]/section[2]/section/div[1]/"
        "fieldset/label[4]"
    )
    for _ in range(10):
        label_estado = page.locator(xpath_label_estado)
        if not label_estado.count():
            label_estado = page.locator("label").filter(
                has_text=re.compile(r"\bEstado\b", re.IGNORECASE)
            ).last

        valor_do_estado = label_estado.locator("xpath=./div/div/div")
        controle_do_estado = label_estado.locator(
            "select, input, [role='combobox']"
        )
        grupos_candidatos = [
            valor_do_estado,
            controle_do_estado,
            page.locator(seletores),
        ]
        for candidatos in grupos_candidatos:
            # Dentro do label, os componentes visuais mais internos costumam
            # aparecer por ultimo e recebem o clique do dropdown.
            indices = range(candidatos.count() - 1, -1, -1)
            for indice in indices:
                candidato = candidatos.nth(indice)
                if candidato.is_visible():
                    campo_uf = candidato
                    break
            if campo_uf:
                break
        if campo_uf:
            break

        # Fallback para componentes cujo campo nao possui "uf" no id/name.
        rotulos = page.locator("label").filter(
            has_text=re.compile(r"^\s*(UF|Estado)\s*:?\s*$", re.IGNORECASE)
        )
        for indice in range(rotulos.count()):
            rotulo = rotulos.nth(indice)
            id_campo = rotulo.get_attribute("for")
            proximos = (
                page.locator(f"#{id_campo}") if id_campo
                else rotulo.locator("xpath=..").locator("select, input, [role='combobox'], button")
            )
            if proximos.count() and proximos.first.is_visible():
                campo_uf = proximos.first
                break
        if campo_uf:
            break
        page.wait_for_timeout(1000)

    if not campo_uf:
        raise RuntimeError("Campo de UF nao foi encontrado apos aguardar a tela de edicao.")

    tag = campo_uf.evaluate("element => element.tagName.toLowerCase()")
    if tag in ("input", "select", "textarea"):
        valor_atual = (campo_uf.input_value() or "").strip()
    else:
        valor_atual = (campo_uf.text_content() or "").strip()
    valor_normalizado = normalizar_texto(valor_atual)
    valores_vazios = {"", "SELECIONE", "SELECIONAR", "UF", "ESTADO"}
    esta_vazio = (
        valor_normalizado in valores_vazios
        or valor_normalizado.startswith("SELECIONE")
    )
    if not esta_vazio:
        print(f"PASSO 8/9: UF ja preenchida com '{valor_atual}'.")
        return

    print("PASSO 8/9: UF vazia. Preenchendo como 'CE'...")
    if tag == "select":
        try:
            campo_uf.select_option("CE")
        except Exception:
            campo_uf.select_option(label=re.compile(r"^\s*CE\s*$", re.IGNORECASE))
        return

    campo_uf.click()
    if tag in ("input", "textarea"):
        campo_uf.fill("CE")
    nome_ce = re.compile(r"^\s*(CE|Cear[aá])\s*$", re.IGNORECASE)
    opcao_ce = page.get_by_role("option", name=nome_ce).last
    try:
        opcao_ce.wait_for(state="visible", timeout=3000)
        opcao_ce.click()
    except Exception:
        page.get_by_text(nome_ce).last.click()


def retornar_para_listagem(page, forcar_recarregamento=False):
    """Garante o retorno a lista sem encerrar toda a automacao por timeout."""
    linhas = page.locator("tbody tr")
    try:
        if linhas.count() and linhas.first.is_visible():
            return True
    except Exception:
        pass

    page.goto("https://hub.sieg.com/GerenciarCNPJ", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("tbody tr:visible", timeout=20000)
        return True
    except Exception:
        print("Nao foi possivel retornar a listagem de empresas.")
        return False


def clicar_cadastrar_certificado_a1(page):
    """Localiza o botao por texto e usa o XPath absoluto como fallback."""
    seletores = [
        "button:has-text('Cadastrar certificado A1')",
        "xpath=/html/body/div[5]/div/div[2]/section[2]/section/div[1]/button",
    ]
    for seletor in seletores:
        botao = page.locator(seletor).first
        try:
            botao.wait_for(state="visible", timeout=5000)
            botao.scroll_into_view_if_needed()
            botao.click()
            return
        except Exception:
            continue
    raise RuntimeError("Botao 'Cadastrar certificado A1' nao foi encontrado.")


def obter_status_certificado(page, linha):
    """Le exclusivamente a td[2] da linha atual."""
    celulas = linha.locator("td")
    if celulas.count() < 2:
        print("  AVISO: td[2] nao foi encontrada; a empresa sera processada.")
        return ""

    # nth(1) corresponde a td[2], pois os indices do Playwright comecam em zero.
    return " ".join(celulas.nth(1).inner_text().split())


def fazer_login_sieg(page):
    """Preenche o login do SIEG com as credenciais configuradas no .env."""
    if not SIEG_EMAIL or not SIEG_SENHA:
        raise RuntimeError("Defina SIEG_EMAIL e SIEG_SENHA no arquivo .env.")

    campo_email = page.locator(
        "input[type='email'], input[name*='email' i], input[id*='email' i]"
    ).first
    campo_senha = page.locator("input[type='password']").first

    if not campo_email.is_visible() or not campo_senha.is_visible():
        print("Sessão do SIEG já está autenticada.")
        return

    campo_email.fill(SIEG_EMAIL)
    campo_senha.fill(SIEG_SENHA)
    botao_login = page.get_by_role(
        "button", name=re.compile(r"entrar|login|acessar", re.IGNORECASE)
    ).first
    botao_login.click()
    page.wait_for_load_state("domcontentloaded")
    print("Login do SIEG realizado automaticamente.")


def ler_senha_arquivo(caminho_arquivo):
    """Lê a senha contida em arquivos .txt ou .docx/.doc."""
    try:
        extensao = caminho_arquivo.suffix.lower()

        if extensao == ".txt":
            with open(caminho_arquivo, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()

        elif extensao in [".docx", ".doc"]:
            doc = Document(caminho_arquivo)
            linhas = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return " ".join(linhas).strip()

    except Exception as e:
        print(f"[ERRO] Falha ao ler arquivo de senha {caminho_arquivo}: {e}")
        return None


def autenticar_google_drive():
    """Autentica no Google Drive e reutiliza o token salvo localmente."""
    credenciais = None
    if ARQUIVO_TOKEN_GOOGLE.exists():
        credenciais = Credentials.from_authorized_user_file(
            ARQUIVO_TOKEN_GOOGLE, ESCOPO_GOOGLE_DRIVE
        )
        if not credenciais.has_scopes(ESCOPO_GOOGLE_DRIVE):
            print("O token atual não possui permissão para gravar o relatório no Drive.")
            credenciais = None

    if not credenciais or not credenciais.valid:
        if credenciais and credenciais.expired and credenciais.refresh_token:
            try:
                credenciais.refresh(Request())
            except RefreshError as erro:
                print(
                    "Token do Google Drive incompatível ou expirado; "
                    "uma nova autorização será solicitada."
                )
                print(f"Detalhe da renovação: {erro}")
                credenciais = None

        if not credenciais or not credenciais.valid:
            if not ARQUIVO_CREDENCIAIS_GOOGLE.exists():
                raise FileNotFoundError(
                    f"Credenciais do Google não encontradas: {ARQUIVO_CREDENCIAIS_GOOGLE}"
                )
            fluxo = InstalledAppFlow.from_client_secrets_file(
                ARQUIVO_CREDENCIAIS_GOOGLE, ESCOPO_GOOGLE_DRIVE
            )
            credenciais = fluxo.run_local_server(port=0)

        ARQUIVO_TOKEN_GOOGLE.write_text(credenciais.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=credenciais)


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


def baixar_arquivo_drive(servico_drive, arquivo):
    """Baixa um arquivo do Drive para o diretório temporário da automação."""
    PASTA_TEMPORARIA_DRIVE.mkdir(parents=True, exist_ok=True)
    destino = PASTA_TEMPORARIA_DRIVE / f"{arquivo['id']}_{arquivo['name']}"
    requisicao = servico_drive.files().get_media(fileId=arquivo["id"])
    with destino.open("wb") as arquivo_local:
        download = MediaIoBaseDownload(arquivo_local, requisicao)
        concluido = False
        while not concluido:
            _, concluido = download.next_chunk()
    return destino


def exportar_google_doc_como_texto(servico_drive, arquivo):
    """Le a senha quando ela esta armazenada como Google Docs nativo."""
    requisicao = servico_drive.files().export_media(
        fileId=arquivo["id"], mimeType="text/plain"
    )
    with tempfile.TemporaryFile() as arquivo_temporario:
        download = MediaIoBaseDownload(arquivo_temporario, requisicao)
        concluido = False
        while not concluido:
            _, concluido = download.next_chunk()
        arquivo_temporario.seek(0)
        return arquivo_temporario.read().decode("utf-8-sig", errors="ignore").strip()


def buscar_arquivos_por_nome_empresa(nome_empresa_alvo, servico_drive, id_pasta_raiz):
    """Busca a pasta da empresa no Drive e baixa o .pfx e a senha."""
    nome_alvo_norm = normalizar_texto(nome_empresa_alvo)

    pastas_empresa = listar_itens_drive(
        servico_drive,
        id_pasta_raiz,
        "application/vnd.google-apps.folder",
    )
    pastas_candidatas = []
    for pasta_empresa in pastas_empresa:
        nome_pasta_norm = normalizar_texto(pasta_empresa["name"])
        if nome_alvo_norm in nome_pasta_norm or nome_pasta_norm in nome_alvo_norm:
            pastas_candidatas.append(pasta_empresa)

    # Prefere o nome exato, mas continua tentando as demais pastas semelhantes
    # quando a primeira nao possui todos os arquivos necessarios.
    pastas_candidatas.sort(
        key=lambda pasta: (
            normalizar_texto(pasta["name"]) != nome_alvo_norm,
            len(normalizar_texto(pasta["name"])),
        )
    )

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

            caminho_pfx = str(baixar_arquivo_drive(servico_drive, arquivos_pfx[0]))
            arquivo_senha = arquivos_senha[0]
            if arquivo_senha.get("mimeType") == "application/vnd.google-apps.document":
                senha = exportar_google_doc_como_texto(servico_drive, arquivo_senha)
            else:
                caminho_senha = baixar_arquivo_drive(servico_drive, arquivo_senha)
                senha = ler_senha_arquivo(caminho_senha)

            if senha:
                return caminho_pfx, senha
            print(f"    Arquivo de senha vazio ou ilegivel: {arquivo_senha['name']}")

    return None, None


# ---------------------------------------------------------
# FLUXO PRINCIPAL DE AUTOMAÇÃO NO SIEG
# ---------------------------------------------------------
def executar_automacao_sieg_cadastro_a1():
    empresas_sem_certificado = []
    id_pasta_raiz = ID_PASTA_DRIVE_CERTIFICADOS
    if not id_pasta_raiz and os.getenv("MODO_AUTOMATICO", "").lower() == "sim":
        raise RuntimeError(
            "Defina GOOGLE_DRIVE_FOLDER_ID no arquivo Auto_NC/.env "
            "com a pasta exclusiva da Auto_NC."
        )
    id_pasta_raiz = id_pasta_raiz or input(
        "Informe o ID ou a URL da pasta raiz do Google Drive: "
    ).strip()
    id_pasta_raiz = extrair_id_pasta_drive(id_pasta_raiz)
    if not id_pasta_raiz:
        raise RuntimeError("O ID da pasta raiz do Google Drive não foi informado.")

    print("Autenticando no Google Drive...")
    servico_drive = autenticar_google_drive()
    salvar_empresas_sem_certificado(empresas_sem_certificado, servico_drive)

    with sync_playwright() as p:
        # Evita que cliques, preenchimentos e selecoes ocorram rapido demais.
        browser = p.chromium.launch(
            headless=False,
            slow_mo=PAUSA_CADA_ACAO_MS,
        )
        page = browser.new_page()

        print("PASSO 1: Acessando o SIEG...")
        page.goto("https://hub.sieg.com/")
        time.sleep(TIME_CURTO)

        fazer_login_sieg(page)
        time.sleep(TIME_CURTO)

        print("\nPASSO 2: Clicando em 'Todos os Serviços'...")
        clicar_com_rolagem(page, "Todos os Serviços")
        time.sleep(TIME_CURTO)

        print("PASSO 3: Clicando em 'Gerenciar CNPJs/CPFs'...")
        clicar_com_rolagem(page, "Gerenciar CNPJs")
        time.sleep(TIME_CURTO)

        page.wait_for_selector("table")

        # ---------------------------------------------------------
        # LOOP DE PÁGINAS (PAGINAÇÃO)
        # ---------------------------------------------------------
        pagina_atual = 1
        
        while True:
            print(f"\n==========================================")
            print(f"📄 INICIANDO PROCESSAMENTO DA PÁGINA {pagina_atual}")
            print(f"==========================================")

            # Abre o seletor de quantidade e escolhe 200 itens por tela.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(TIME_CURTO)

            seletor_quantidade = page.locator(
                "xpath=//*[@id='app']/main/section/div/section/section[2]/"
                "div[1]/section/div[4]/div[2]/div/nav/div/div/div[2]/div[2]/div/div/div"
            )
            seletor_quantidade.wait_for(state="visible", timeout=10000)
            seletor_quantidade.click()

            opcao_200 = page.locator(
                "xpath=//*[@id='app']/main/section/div/section/section[2]/"
                "div[1]/section/div[4]/div[2]/div/nav/div/div/div[2]/div[2]/"
                "teleport/ul/li[5]"
            )
            opcao_200.wait_for(state="visible", timeout=10000)
            opcao_200.click()
            time.sleep(TIME_CURTO)
            page.wait_for_selector("table")

            linhas_empresas = page.locator("tbody tr:visible").all()
            print(f"Total de empresas encontradas na lista visível: {len(linhas_empresas)}")

            for index, linha in enumerate(linhas_empresas):
                print(f"\n--- Processando linha {index + 1} de {len(linhas_empresas)} (Pág. {pagina_atual}) ---")

                try:
                    # A página é recarregada após cada empresa; obtenha a linha atual novamente.
                    page.wait_for_selector("tbody tr:visible")
                    linha = page.locator("tbody tr:visible").nth(index)
                    linha.wait_for(state="visible")
                    linha.scroll_into_view_if_needed()
                    texto_linha = linha.inner_text()

                    # REGRA 2: Checar se a empresa NÃO possui certificado (Símbolo "-")
                    # Analisa as colunas da tabela
                    partes_linha = [p.strip() for p in texto_linha.split("\n") if p.strip()]

                    # Filtra o nome da empresa
                    nome_empresa = None
                    for parte in partes_linha:
                        if not re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", parte) and not re.search(r"\d{2}/\d{2}/\d{4}", parte):
                            if len(parte) > 3 and "COMPLETO" not in parte.upper():
                                nome_empresa = parte
                                break

                    if not nome_empresa:
                        continue

                    # Verifica apenas a coluna de certificado. Outras colunas
                    # tambem podem conter "No prazo" ou "Vencido".
                    status_certificado = obter_status_certificado(page, linha)
                    status_normalizado = normalizar_texto(status_certificado)
                    print(f"  Status lido APENAS em td[2]: '{status_certificado or '-'}'")
                    estados_com_certificado = ("NO PRAZO", "VENCIDA", "VENCIDO")
                    possui_certificado = any(
                        estado in status_normalizado
                        for estado in estados_com_certificado
                    )

                    if possui_certificado:
                        print(f"⏩ PULANDO: Empresa '{nome_empresa}' já possui certificado cadastrado.")
                        continue

                    print(f"🔍 Empresa sem certificado identificada: {nome_empresa}")
                    cnpj_encontrado = re.search(
                        r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}", texto_linha
                    )
                    empresa_sem_certificado = {
                        "nome": nome_empresa,
                        "cnpj": re.sub(r"\D", "", cnpj_encontrado.group(0))
                        if cnpj_encontrado else "",
                        "motivo": "Empresa sem certificado cadastrado no SIEG",
                    }
                    empresas_sem_certificado.append(empresa_sem_certificado)
                    salvar_empresas_sem_certificado(
                        empresas_sem_certificado, servico_drive
                    )

                    # REGRA 5: Buscar pasta da empresa no Drive
                    caminho_pfx, senha_certificado = buscar_arquivos_por_nome_empresa(
                        nome_empresa, servico_drive, id_pasta_raiz
                    )

                    if not caminho_pfx or not senha_certificado:
                        print(f"⚠️ PULANDO: A empresa '{nome_empresa}' NÃO possui pasta/arquivos no Drive.")
                        continue

                    print(f"  └─ Certificado local: {caminho_pfx}")

                    # PASSOS 6/7: fluxo validado no projeto preservado.
                    if not abrir_edicao_empresa(page, linha):
                        raise RuntimeError("Nao foi possivel abrir a edicao da empresa.")
                    time.sleep(TIME_CURTO)

                    # PASSO 8 e 9: Preencher UF 'CE' se estiver vazia
                    preencher_uf_se_necessario(page)
                    time.sleep(TIME_CURTO)

                    # PASSO 10: Salvar e continuar
                    clicar_com_rolagem(page, "Salvar e continuar")
                    time.sleep(TIME_CURTO)

                    # REGRA 3: Clicar no botão "Cadastrar certificado A1"
                    print("PASSO 11: Clicando no botão 'Cadastrar certificado A1'...")
                    # Tenta clicar usando o seletor XPath enviado ou o texto direto do botão
                    clicar_cadastrar_certificado_a1(page)
                    time.sleep(TIME_CURTO)

                    # PASSO 12-16: Upload do arquivo .pfx
                    print(f"PASSO 12-16: Enviando arquivo .pfx...")
                    # Inputs de upload normalmente ficam ocultos; nao tente
                    # rolar ate eles. O set_input_files funciona diretamente.
                    campo_file = page.locator("input[type='file']").last
                    campo_file.wait_for(state="attached", timeout=15000)
                    campo_file.set_input_files(caminho_pfx)
                    time.sleep(TIME_CURTO)

                    # PASSO 17: Digitar a senha
                    print("PASSO 17: Inserindo a senha do certificado...")
                    campo_pass = page.locator("input[type='password']").first
                    campo_pass.scroll_into_view_if_needed()
                    campo_pass.fill(senha_certificado)
                    time.sleep(TIME_CURTO)

                    # TIMEEEEE: Pausa para validação do PFX
                    print(f"⏳ TIMEEEEE: Aguardando {TIME_LONGO} segundos para processamento...")
                    time.sleep(TIME_LONGO)

                    # PASSO 19: Clicar na caixinha de automação
                    print("PASSO 19: Marcando caixinha de automação...")
                    chk_automacao = page.locator("input.d-checkbox.su-checkbox").first
                    if chk_automacao.is_visible():
                        chk_automacao.scroll_into_view_if_needed()
                        if not chk_automacao.is_checked():
                            chk_automacao.check()
                    time.sleep(TIME_CURTO)

                    # PASSO 20 a 22: Salvar e continuar
                    for i in range(1, 4):
                        print(f"PASSO {19+i}: Clicando em 'Salvar e continuar' ({i}/3)...")
                        clicar_com_rolagem(page, "Salvar e continuar")
                        time.sleep(TIME_CURTO)

                    # Checa opção NFS-e Portal Nacional
                    try:
                        input_nfse = page.locator("label:has-text('NFS-e Portal Nacional') input, input[name*='nfse']").first
                        if input_nfse.is_visible() and not input_nfse.is_checked():
                            print("PASSO: Ativando a opção 'NFS-e Portal Nacional'...")
                            input_nfse.check()
                            time.sleep(TIME_CURTO)
                    except Exception:
                        pass

                    # PASSO 23: Concluir
                    print("PASSO 23: Clicando em 'Concluir'...")
                    clicar_com_rolagem(page, "Concluir")
                    time.sleep(TIME_CURTO)

                    # PASSO 24: Confirmar e finalizar
                    print("PASSO 24: Clicando em 'Confirmar e finalizar'...")
                    clicar_com_rolagem(page, "Confirmar e finalizar")

                    print(f"⏳ Aguardando {TIME_FINAL} segundos para gravar no servidor...")
                    time.sleep(TIME_FINAL)

                    print(f"✅ Sucesso: Certificado A1 da empresa '{nome_empresa}' cadastrado!")
                    empresas_sem_certificado = [
                        item for item in empresas_sem_certificado
                        if normalizar_texto(item["nome"]) != normalizar_texto(nome_empresa)
                    ]
                    salvar_empresas_sem_certificado(
                        empresas_sem_certificado, servico_drive
                    )

                except Exception as err:
                    print(f"❌ OCORREU UM ERRO na empresa '{nome_empresa}': {err}")
                    print("Cancelando edição e retornando para continuar...")

                    try:
                        btn_cancelar = page.locator("button:has-text('Cancelar'), text=Cancelar").first
                        if btn_cancelar.is_visible():
                            btn_cancelar.click()
                            time.sleep(TIME_CURTO)
                    except Exception:
                        pass

                    if not retornar_para_listagem(page, forcar_recarregamento=True):
                        print("Automacao interrompida para evitar novo timeout.")
                        browser.close()
                        return
                    time.sleep(TIME_CURTO)
                    continue

                # Retorna para a listagem para processar o próximo item
                if not retornar_para_listagem(page):
                    print("Automacao interrompida para evitar novo timeout.")
                    browser.close()
                    return
                time.sleep(TIME_CURTO)

            # ---------------------------------------------------------
            # REGRA 4: TROCA DE PÁGINA (SETINHA DA PAGINAÇÃO)
            # ---------------------------------------------------------
            print("\n🔄 Finalizou o processamento da página atual. Tentando ir para a próxima...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(TIME_CURTO)

            # Localiza o botão da setinha de 'Próxima página' no rodapé
            btn_proxima_pagina = page.locator("button.btn-next, .pagination-next, button:has(svg[data-icon='chevron-right']), button[aria-label='Next page']").first

            if btn_proxima_pagina.is_visible() and btn_proxima_pagina.is_enabled():
                print("➡️ Clicando na seta para ir para a PRÓXIMA PÁGINA...")
                btn_proxima_pagina.click()
                pagina_atual += 1
                time.sleep(3.0)  # Aguarda carregar a nova página
            else:
                print("\n🏁 Não há mais páginas para avançar. Automação concluída!")
                break

        salvar_empresas_sem_certificado(empresas_sem_certificado, servico_drive)
        print("\n🎉 Processo finalizado com sucesso em todas as páginas!")
        browser.close()


if __name__ == "__main__":
    executar_automacao_sieg_cadastro_a1()
