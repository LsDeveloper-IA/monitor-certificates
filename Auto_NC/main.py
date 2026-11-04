import os
import sys
from pathlib import Path

RAIZ = str(Path(__file__).resolve().parents[1])


def _resolver_pasta_storage():
    """Retorna a pasta de dados gerados, fora do codigo versionado."""
    configurada = os.getenv("STORAGE_DIR", "").strip()
    if configurada:
        caminho = Path(configurada).expanduser()
        if not caminho.is_absolute():
            caminho = Path(RAIZ) / caminho
        return caminho.resolve()
    return Path(RAIZ) / "storage"


PASTA_STORAGE = _resolver_pasta_storage()
PASTA_SEGREDOS = PASTA_STORAGE / "secrets" / "auto_nc"
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from sieg_comum.identidade import normalizar_texto
from sieg_comum.configuracao import ler_inteiro_nao_negativo
from sieg_comum.navegacao import clicar_com_rolagem, abrir_edicao_empresa, preencher_uf_se_necessario
from sieg_comum.sessao import realizar_login_sieg
from sieg_comum import drive as cliente_drive

import json
import re
import tempfile
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from googleapiclient.http import MediaFileUpload


def carregar_arquivo_env():
    """Carrega variáveis .env sem substituir valores já definidos no ambiente."""
    arquivos_env = [
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).with_name(".env"),
    ]

    for arquivo_env in arquivos_env:
        if not arquivo_env.exists():
            continue

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
# Configure o ID da pasta raiz no Google Drive e coloque credentials.json em storage/secrets/auto_nc.
ID_PASTA_DRIVE_CERTIFICADOS = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
ARQUIVO_CREDENCIAIS_GOOGLE = Path(
    os.getenv("GOOGLE_DRIVE_CREDENTIALS", str(PASTA_SEGREDOS / "credentials.json"))
)
ARQUIVO_TOKEN_GOOGLE = Path(
    os.getenv("GOOGLE_DRIVE_TOKEN", str(PASTA_SEGREDOS / "token.json"))
)
ESCOPO_GOOGLE_DRIVE = ["https://www.googleapis.com/auth/drive"]
ID_PASTA_DRIVE_RELATORIO = os.getenv("AUTO_NC_REPORT_FOLDER_ID", "").strip()
PASTA_TEMPORARIA_DRIVE = Path(tempfile.gettempdir()) / "auto_nc_drive"
ARQUIVO_RELATORIO_SEM_CERTIFICADO = Path(
    os.getenv(
        "AUTO_NC_RELATORIO_PATH",
        str(PASTA_STORAGE / "auto_nc" / "empresas_sem_certificado.json"),
    )
)
ARQUIVO_EMPRESAS_SIEG = PASTA_STORAGE / "auto_nc" / "empresas_sieg.json"
SIEG_EMAIL = os.getenv("SIEG_EMAIL", "")
SIEG_SENHA = os.getenv("SIEG_SENHA", "")

# Execução direcionada: quando informado, processa somente a empresa alvo.
# Útil para validar uma empresa sem alterar as demais.
EMPRESA_ALVO = normalizar_texto(os.getenv("AUTO_NC_EMPRESA_ALVO", ""))
CNPJ_ALVO = re.sub(r"\D", "", os.getenv("AUTO_NC_CNPJ_ALVO", ""))
MODO_ALVO = bool(EMPRESA_ALVO or CNPJ_ALVO)

# Tempos de espera (em segundos)
TIME_CURTO = 2.5   # Pausa entre as etapas principais
PAUSA_CADA_ACAO_MS = ler_inteiro_nao_negativo("SIEG_SLOW_MO_MS")
TIME_LONGO = 6.0   # Pausa para validação do PFX (TIMEEEEE)
TIME_FINAL = 15.0  # Pausa após "Confirmar e finalizar"


# ---------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------


def ler_empresas_sieg_da_pagina(page):
    """Lê a página inteira de uma vez, antes de editar qualquer empresa."""
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_function("""() => {
        const rows = [...document.querySelectorAll('table tbody tr')]
            .filter(row => row.getBoundingClientRect().height);
        return rows.length && rows.every(row => !/carregando/i.test(row.innerText));
    }""", timeout=30000)
    linhas = page.locator("table:visible").first.locator("tbody").evaluate("""body =>
        [...body.querySelectorAll('tr')].map(row => {
            const cells = [...row.querySelectorAll('td')];
            return {
                texto: row.innerText,
                nome: cells[0]?.innerText || '',
                ativo_sieg: cells[6]?.querySelector('input')?.checked === true,
            };
        })
    """)
    padrao_documento = re.compile(
        r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{14}\b"
    )
    empresas = []
    for linha in linhas:
        documento = padrao_documento.search(linha["nome"])
        empresas.append({
            "nome": re.split(r"\b(?:CNPJ|CPF):", linha["nome"], maxsplit=1)[0].strip(),
            "cnpj": re.sub(r"\D", "", documento.group()) if documento else "",
            "ativo_sieg": linha["ativo_sieg"],
        })
    return empresas


def salvar_base_empresas_sieg(empresas, total_esperado):
    """Publica os CNPJs ativos após percorrer todas as páginas do SIEG."""
    if MODO_ALVO:
        print("Execução direcionada: base de empresas do SIEG não será alterada.")
        return False
    identidades = {(str(item.get("cnpj") or ""), item.get("nome") or "") for item in empresas}
    if total_esperado is None or len(empresas) != total_esperado or len(identidades) != total_esperado:
        print("Base SIEG não atualizada: a leitura não cobriu todos os cadastros. Mantida a última base completa.")
        return False
    ativas = {}
    for empresa in empresas:
        documento = re.sub(r"\D", "", str(empresa.get("cnpj") or ""))
        if empresa.get("ativo_sieg") is not True or len(documento) != 14:
            continue
        ativas[documento] = {**empresa, "cnpj": documento}
    dados = {
        "completo": True,
        "atualizado_em": datetime.now().isoformat(),
        "empresas": list(ativas.values()),
    }
    ARQUIVO_EMPRESAS_SIEG.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_EMPRESAS_SIEG.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporario, ARQUIVO_EMPRESAS_SIEG)
    return True


def salvar_empresas_sem_certificado(empresas, servico_drive=None):
    """Disponibiliza no painel a lista parcial da execução atual."""
    if MODO_ALVO:
        print("Execução direcionada: relatório de empresas sem certificado não será alterado.")
        return
    unicas = {
        re.sub(r"\D", "", str(item.get("cnpj") or "")) or normalizar_texto(item["nome"]): item
        for item in empresas
    }
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
    if not ID_PASTA_DRIVE_RELATORIO:
        raise RuntimeError(
            "Defina AUTO_NC_REPORT_FOLDER_ID no arquivo Auto_NC/.env."
        )
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


XPATH_BOTAO_PRINCIPAL_MODAL = (
    "xpath=/html/body/div[5]/div/div[2]/section[2]/section/div[1]/button"
)


def clicar_botao_principal_modal(page, texto_alternativo):
    """Clica no botao principal do modal, usando o texto como fallback."""
    try:
        botao = page.locator(XPATH_BOTAO_PRINCIPAL_MODAL).first
        botao.wait_for(state="visible", timeout=5000)
        botao.scroll_into_view_if_needed()
        botao.click()
        return True
    except Exception:
        return clicar_com_rolagem(page, texto_alternativo)


def clicar_cadastrar_certificado_a1(page):
    """Localiza o botao por texto e usa o XPath absoluto como fallback."""
    seletores = [
        "button:has-text('Cadastrar certificado A1')",
        XPATH_BOTAO_PRINCIPAL_MODAL,
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


# ---------------------------------------------------------
# FLUXO PRINCIPAL DE AUTOMAÇÃO NO SIEG
# ---------------------------------------------------------

def fazer_login_sieg(page):
    if not realizar_login_sieg(page, SIEG_EMAIL, SIEG_SENHA):
        raise RuntimeError("Falha ao autenticar no SIEG.")


def autenticar_google_drive():
    return cliente_drive.autenticar_drive(
        ARQUIVO_CREDENCIAIS_GOOGLE, ARQUIVO_TOKEN_GOOGLE, ESCOPO_GOOGLE_DRIVE,
    )


def buscar_arquivos_por_nome_empresa(nome_empresa_alvo, servico_drive, id_pasta_raiz):
    return cliente_drive.buscar_arquivos_por_nome_empresa(
        nome_empresa_alvo, servico_drive, id_pasta_raiz, PASTA_TEMPORARIA_DRIVE,
    )


def executar_automacao_sieg_cadastro_a1():
    empresas_sem_certificado = []
    empresas_sieg = []
    total_empresas_sieg = None
    id_pasta_raiz = ID_PASTA_DRIVE_CERTIFICADOS
    ausentes = [
        nome for nome, valor in (
            ("GOOGLE_DRIVE_FOLDER_ID", id_pasta_raiz),
            ("AUTO_NC_REPORT_FOLDER_ID", ID_PASTA_DRIVE_RELATORIO),
        ) if not valor
    ]
    if ausentes:
        raise RuntimeError(
            f"Defina {', '.join(ausentes)} no arquivo Auto_NC/.env."
        )
    id_pasta_raiz = extrair_id_pasta_drive(id_pasta_raiz)
    if not id_pasta_raiz:
        raise RuntimeError("O ID da pasta raiz do Google Drive não foi informado.")

    print("Autenticando no Google Drive...")
    servico_drive = autenticar_google_drive()
    salvar_empresas_sem_certificado(empresas_sem_certificado, servico_drive)

    with sync_playwright() as p:
        # Evita que cliques, preenchimentos e selecoes ocorram rapido demais.
        browser = p.chromium.launch(
            headless=True,
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

            nav_paginacao = None
            for section_index in (2, 3):
                for div_index in (4, 5, 3, 6, 2, 7, 8):
                    candidato = page.locator(
                        "xpath=//*[@id='app']/main/section/div/section/"
                        "section[%d]/div[1]/section/div[%d]/div[2]/div/nav"
                        % (section_index, div_index)
                    )
                    if candidato.count() > 0:
                        nav_paginacao = candidato.last
                        break
                if nav_paginacao is not None:
                    break

            if nav_paginacao is None or nav_paginacao.count() == 0:
                todos_navs = page.locator("nav")
                for indice in range(todos_navs.count()):
                    nav = todos_navs.nth(indice)
                    try:
                        texto_nav = nav.inner_text()
                    except Exception:
                        continue
                    if re.search(r"\bde\s+[\d.,]+", texto_nav):
                        nav_paginacao = nav
                if nav_paginacao is None and todos_navs.count() > 0:
                    nav_paginacao = todos_navs.last

            if nav_paginacao is not None and nav_paginacao.count() > 0:
                try:
                    nav_paginacao.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    if nav_paginacao.get_by_text("200", exact=True).count() == 0:
                        controle = nav_paginacao.get_by_text("50", exact=True)
                        if controle.count() == 0:
                            controle = page.get_by_text("50", exact=True)
                        clicou_controle = False
                        for indice in range(controle.count() - 1, -1, -1):
                            candidato = controle.nth(indice)
                            if candidato.is_visible() and candidato.is_enabled():
                                candidato.scroll_into_view_if_needed()
                                candidato.click(force=True)
                                clicou_controle = True
                                break
                        if clicou_controle:
                            time.sleep(TIME_CURTO)
                            opcao_200 = None
                            for xpath_opcao in (
                                "//*[@id='app']/main/section/div/section/section[2]/"
                                "div[1]/section/div[4]/div[2]/div/nav/div/div/div[2]/"
                                "div[2]/teleport/ul/li[5]",
                            ):
                                candidato_opcao = page.locator("xpath=" + xpath_opcao)
                                if candidato_opcao.count() > 0:
                                    opcao_200 = candidato_opcao.last
                                    break
                            if opcao_200 is None or opcao_200.count() == 0:
                                opcoes = page.locator("li:visible").filter(
                                    has_text=re.compile(r"^\s*200\s*$")
                                )
                                if opcoes.count() > 0:
                                    opcao_200 = opcoes.last
                            if opcao_200 is not None and opcao_200.count() > 0:
                                try:
                                    opcao_200.click(force=True)
                                except Exception:
                                    pass
                            time.sleep(TIME_CURTO)
                except Exception:
                    pass

            time.sleep(TIME_CURTO)
            page.wait_for_selector("table")

            empresas_sieg.extend(ler_empresas_sieg_da_pagina(page))
            if total_empresas_sieg is None:
                rodape = None
                for section_index in (2, 3):
                    for div_index in (4, 5, 3, 6, 2, 7, 8):
                        candidato = page.locator(
                            "xpath=//*[@id='app']/main/section/div/section/"
                            "section[%d]/div[1]/section/div[%d]/div[2]/div/nav"
                            % (section_index, div_index)
                        )
                        if candidato.count() > 0:
                            rodape = candidato.last
                            break
                    if rodape is not None:
                        break
                if rodape is None or rodape.count() == 0:
                    todos_navs = page.locator("nav")
                    for indice in range(todos_navs.count()):
                        nav = todos_navs.nth(indice)
                        try:
                            texto_nav = nav.inner_text()
                        except Exception:
                            continue
                        if re.search(r"\bde\s+[\d.,]+", texto_nav):
                            rodape = nav
                    if rodape is None and todos_navs.count() > 0:
                        rodape = todos_navs.last
                try:
                    rodape_texto = rodape.inner_text() if rodape is not None else ""
                except Exception:
                    rodape_texto = ""
                total_encontrado = re.search(r"\bde\s+([\d.,]+)", rodape_texto, re.IGNORECASE)
                if total_encontrado:
                    total_empresas_sieg = int(re.sub(r"\D", "", total_encontrado.group(1)))
            linhas_empresas = page.locator("tbody tr:visible").all()
            print(f"Total de empresas encontradas na lista visível: {len(linhas_empresas)}")

            alvo_processado = False
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

                    cnpj_encontrado = re.search(
                        r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}", texto_linha
                    )
                    cnpj_linha = (
                        re.sub(r"\D", "", cnpj_encontrado.group(0))
                        if cnpj_encontrado else ""
                    )

                    if MODO_ALVO:
                        corresponde = (
                            (not CNPJ_ALVO or cnpj_linha == CNPJ_ALVO)
                            and (
                                not EMPRESA_ALVO
                                or normalizar_texto(nome_empresa) == EMPRESA_ALVO
                            )
                        )
                        if not corresponde:
                            continue
                        alvo_processado = True
                        print(f"🎯 Empresa alvo localizada: {nome_empresa}")

                    # Confere "Ativo na Sieg" na td[7] da empresa atual.
                    campo_ativo_sieg = linha.locator("xpath=./td[7]/input")
                    if campo_ativo_sieg.count() != 1 or not campo_ativo_sieg.is_checked():
                        print(
                            f"⏩ PULANDO: Empresa '{nome_empresa}' está com "
                            "'Ativo na Sieg' desmarcado ou indisponível."
                        )
                        if MODO_ALVO:
                            break
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
                        if MODO_ALVO:
                            break
                        continue

                    print(f"🔍 Empresa sem certificado identificada: {nome_empresa}")
                    empresa_sem_certificado = {
                        "nome": nome_empresa,
                        "cnpj": cnpj_linha,
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
                        if MODO_ALVO:
                            break
                        continue

                    print(f"  └─ Certificado local: {caminho_pfx}")

                    # PASSOS 6/7: fluxo validado no projeto preservado.
                    if not abrir_edicao_empresa(page, linha):
                        raise RuntimeError("Nao foi possivel abrir a edicao da empresa.")
                    time.sleep(TIME_CURTO)

                    # PASSO 8 e 9: Preencher UF 'CE' se estiver vazia
                    preencher_uf_se_necessario(page, "CE")
                    time.sleep(TIME_CURTO)

                    # PASSO 10: Salvar e continuar
                    clicar_botao_principal_modal(page, "Salvar e continuar")
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

                    if MODO_ALVO:
                        break

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
                    if MODO_ALVO and alvo_processado:
                        break
                    continue

                # Retorna para a listagem para processar o próximo item
                if not retornar_para_listagem(page):
                    print("Automacao interrompida para evitar novo timeout.")
                    browser.close()
                    return
                time.sleep(TIME_CURTO)

            if MODO_ALVO and alvo_processado:
                print("Execução direcionada concluída: encerrando após a empresa alvo.")
                break

            # ---------------------------------------------------------
            # REGRA 4: TROCA DE PÁGINA (SETINHA DA PAGINAÇÃO)
            # ---------------------------------------------------------
            print("\n🔄 Finalizou o processamento da página atual. Tentando ir para a próxima...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(TIME_CURTO)

            # A seta é o último botão; tenta localizar a navegação de forma resiliente.
            btn_proxima_pagina = None
            for section_index in (2, 3):
                for div_index in (4, 5, 3, 6, 2, 7, 8):
                    candidato = page.locator(
                        "xpath=//*[@id='app']/main/section/div/section/"
                        "section[%d]/div[1]/section/div[%d]/div[2]/div/nav/"
                        "div/div/div[2]/div[1]/button[last()]"
                        % (section_index, div_index)
                    )
                    if candidato.count() > 0:
                        btn_proxima_pagina = candidato.last
                        break
                if btn_proxima_pagina is not None:
                    break
            if btn_proxima_pagina is None or btn_proxima_pagina.count() == 0:
                btn_proxima_pagina = page.locator("nav button").last

            if btn_proxima_pagina.is_visible() and btn_proxima_pagina.is_enabled():
                print("➡️ Clicando na seta para ir para a PRÓXIMA PÁGINA...")
                btn_proxima_pagina.click()
                pagina_atual += 1
                time.sleep(3.0)  # Aguarda carregar a nova página
            else:
                print("\n🏁 Não há mais páginas para avançar. Automação concluída!")
                break

        salvar_base_empresas_sieg(empresas_sieg, total_empresas_sieg)
        salvar_empresas_sem_certificado(empresas_sem_certificado, servico_drive)
        if MODO_ALVO:
            if alvo_processado:
                print("\n🎯 Execução direcionada finalizada para a empresa alvo.")
            else:
                print("\n⚠️ Empresa alvo não encontrada na listagem do SIEG.")
        else:
            print("\n🎉 Processo finalizado com sucesso em todas as páginas!")
        browser.close()


if __name__ == "__main__":
    executar_automacao_sieg_cadastro_a1()
