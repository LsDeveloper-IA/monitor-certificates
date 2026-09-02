import re
import time

from playwright.sync_api import expect

from utilitarios import extrair_cnpj


def aguardar_interface_pronta(page, timeout=15000):
    """Espera a rede estabilizar e indicadores visíveis de carregamento sumirem."""
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout, 5000))
    except Exception:
        pass

    page.wait_for_function(
        """
        () => {
            const seletores = [
                '[aria-busy="true"]',
                '[class*="loading"]',
                '[class*="spinner"]',
                '.su-loading',
                '.su-spinner'
            ];
            return !seletores.some(seletor =>
                Array.from(document.querySelectorAll(seletor)).some(elemento => {
                    const estilo = getComputedStyle(elemento);
                    const caixa = elemento.getBoundingClientRect();
                    return estilo.visibility !== 'hidden'
                        && estilo.display !== 'none'
                        && caixa.width > 0
                        && caixa.height > 0;
                })
            );
        }
        """,
        timeout=timeout,
    )


def clicar_com_rolagem(page, seletor, tentativas=5, scroll=350):
    """Tenta clicar em um elemento, rolando a página até encontrá-lo."""
    for i in range(tentativas):
        try:
            if not seletor.startswith((".", "#", "input", "button", "[", "div", "xpath")):
                candidatos = page.get_by_text(re.compile(re.escape(seletor), re.IGNORECASE))
            else:
                candidatos = page.locator(seletor)

            for indice in range(candidatos.count() - 1, -1, -1):
                elemento = candidatos.nth(indice)
                if not elemento.is_visible() or not elemento.is_enabled():
                    continue
                elemento.scroll_into_view_if_needed()
                elemento.click()
                try:
                    aguardar_interface_pronta(page)
                except Exception:
                    pass
                return True
        except Exception:
            pass
        page.evaluate(f"window.scrollBy(0, {scroll})")
    print(f"❌ Não foi possível clicar em '{seletor}'")
    return False


def realizar_login_sieg(page, email, senha):
    """Preenche e submete o formulário de login."""
    print("🔑 Realizando login...")
    try:
        campo_email = page.locator("input[type='email'], input[placeholder*='e-mail']").first
        campo_email.wait_for(state="visible", timeout=60000)
        campo_email.fill(email)

        campo_senha = page.locator("input[type='password'], input[placeholder*='senha']").first
        campo_senha.fill(senha)

        btn_entrar = page.locator("button:has-text('Entrar'), button:has-text('Acessar')").first
        if btn_entrar.is_visible():
            btn_entrar.click()
        else:
            page.keyboard.press("Enter")
        page.get_by_text("Todos os serviços", exact=True).wait_for(
            state="visible", timeout=100000
        )
        return True
    except Exception as e:
        print(f"❌ Falha no login: {e}")
        return False


def aplicar_filtro_vencidos(page):
    """Aplica o filtro de certificado vencido."""
    print("PASSO 4: Clicando em 'Adicionar Filtros'...")
    if not clicar_com_rolagem(page, "Adicionar Filtros"):
        raise RuntimeError("Botão 'Adicionar Filtros' não encontrado")
    page.wait_for_timeout(700)

    print("PASSO 5: Filtrando 'Situação' -> 'Certificado Vencido'...")
    campo_situacao = page.locator(
        "xpath=//*[@id='app']/main/section/div/section/section[2]/div[1]/"
        "section/section[2]/div/div[1]/teleport/ul/li[5]"
    )
    if campo_situacao.count() == 0:
        nome_situacao = re.compile(r"situação", re.IGNORECASE)
        campo_situacao = page.get_by_role("button", name=nome_situacao)
    if campo_situacao.count() == 0:
        campo_situacao = page.get_by_role("menuitem", name=nome_situacao)
    if campo_situacao.count() == 0:
        campo_situacao = page.get_by_role("option", name=nome_situacao)
    if campo_situacao.count() == 0:
        campo_situacao = page.locator(
            "button:visible, [role='button']:visible, "
            "[role='menuitem']:visible, [role='option']:visible, div.input-group:visible"
        ).filter(
            has_text=nome_situacao
        )
    if campo_situacao.count() == 0:
        campo_situacao = page.get_by_text("Situação", exact=True)

    clicou_situacao = False
    for indice in range(campo_situacao.count() - 1, -1, -1):
        candidato = campo_situacao.nth(indice)
        if candidato.is_visible() and candidato.is_enabled():
            candidato.scroll_into_view_if_needed()
            candidato.click(force=True)
            clicou_situacao = True
            break
    if not clicou_situacao:
        raise RuntimeError("Campo/filtro 'Situação' não encontrado ou não habilitado")

    print("  └─ Fechando o menu intermediário...")
    page.mouse.click(5, 5)
    page.wait_for_timeout(300)

    print("  └─ Abrindo novamente o campo 'Situação'...")
    seletor_situacao = (
        "div.flex.justify-between.cursor-pointer:has(span:text-is('Situação'))"
    )
    campo_situacao_barra = page.locator(
        f"teleport {seletor_situacao}"
    )
    if campo_situacao_barra.count() == 0:
        campo_situacao_barra = page.locator(seletor_situacao)
    if campo_situacao_barra.count() == 0:
        campo_situacao_barra = page.locator(
            "xpath=//*[@id='app']/main/section/div/section/section[2]/div[1]/"
            "section/section[2]/section/teleport//div[contains(@class, 'cursor-pointer')]"
            "[.//span[normalize-space()='Situação']]"
        )
    campo_situacao_barra.last.wait_for(state="visible", timeout=10000)
    campo_situacao_barra.last.scroll_into_view_if_needed()
    campo_situacao_barra.last.click(force=True)

    page.wait_for_timeout(500)
    opcao_vencido = page.locator(
        "[role='option']:visible, [role='menuitem']:visible, li:visible"
    ).filter(has_text=re.compile(r"certificado\s+vencido", re.IGNORECASE))
    clicou_opcao = False
    for indice in range(opcao_vencido.count() - 1, -1, -1):
        candidato = opcao_vencido.nth(indice)
        if candidato.is_visible() and candidato.is_enabled():
            candidato.click(force=True)
            clicou_opcao = True
            break

    if not clicou_opcao:
        clicou_opcao = page.evaluate(
            """
            () => {
                const normalizar = texto => (texto || '').replace(/\\s+/g, ' ').trim();
                const visivel = elemento => {
                    const estilo = getComputedStyle(elemento);
                    const caixa = elemento.getBoundingClientRect();
                    return estilo.display !== 'none' && estilo.visibility !== 'hidden'
                        && caixa.width > 0 && caixa.height > 0;
                };
                const textoOpcao = /certificado\\s+vencido/i;
                const elementos = Array.from(document.querySelectorAll(
                    '[role="option"], [role="menuitem"], li, button, span, div'
                ));
                const texto = elementos.find(elemento =>
                    visivel(elemento) && textoOpcao.test(normalizar(elemento.innerText))
                );
                if (!texto) return false;
                const clicavel = texto.closest(
                    '[role="option"], [role="menuitem"], li, button'
                ) || texto;
                clicavel.click();
                return true;
            }
            """
        )

    if not clicou_opcao:
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        clicou_opcao = True

    if not clicou_opcao:
        raise RuntimeError("Opção 'Certificado Vencido' não encontrada no filtro Situação")
    aguardar_interface_pronta(page)
    page.locator("table:visible").first.wait_for(state="visible", timeout=15000)


def alterar_paginacao_para_200(page):
    """Altera o número de itens por página para 200."""
    print("\n📄 Alterando a exibição da tabela para 200 itens por página...")
    try:
            page.evaluate(
                """
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                    for (const elemento of document.querySelectorAll('*')) {
                        if (elemento.scrollHeight > elemento.clientHeight) {
                            elemento.scrollTop = elemento.scrollHeight;
                        }
                    }
                }
                """
            )
            page.keyboard.press("End")
            page.wait_for_timeout(500)

            xpath_nav_paginacao = (
                "//*[@id='app']/main/section/div/section/section[2]/div[1]/"
                "section/div[4]/div[2]/div/nav"
            )
            nav_paginacao = page.locator(f"xpath={xpath_nav_paginacao}")
            nav_paginacao.wait_for(state="attached", timeout=10000)

            # A tabela pode estar dentro de um contêiner com rolagem própria.
            # Leva todos os ancestrais roláveis ao fim e posiciona o nav na tela.
            nav_paginacao.evaluate(
                """
                elemento => {
                    let ancestral = elemento.parentElement;
                    while (ancestral) {
                        if (ancestral.scrollHeight > ancestral.clientHeight) {
                            ancestral.scrollTop = ancestral.scrollHeight;
                        }
                        ancestral = ancestral.parentElement;
                    }
                    elemento.scrollIntoView({block: 'center', inline: 'nearest'});
                }
                """
            )
            nav_paginacao.scroll_into_view_if_needed()
            page.wait_for_timeout(700)

            print("  ├─ Abrindo o seletor de paginação em '50'...")
            xpath_controle_paginacao = (
                "//*[@id='app']/main/section/div/section/section[2]/div[1]/"
                "section/div[4]/div[2]/div/nav/div/div/div[2]/div[2]"
            )
            btn_paginacao = page.locator(f"xpath={xpath_controle_paginacao}")
            if btn_paginacao.count() == 0:
                btn_paginacao = page.get_by_text("50", exact=True)
            clicou_paginacao = False
            for indice in range(btn_paginacao.count() - 1, -1, -1):
                candidato = btn_paginacao.nth(indice)
                if candidato.is_visible() and candidato.is_enabled():
                    candidato.scroll_into_view_if_needed()
                    candidato.click(force=True)
                    clicou_paginacao = True
                    break
            if not clicou_paginacao:
                raise RuntimeError("Controle da paginação '50' não encontrado")

            # Assim como o campo Situação, a lista é criada em um portal
            # somente depois do clique no valor atual.
            page.wait_for_timeout(500)
            print("  ├─ Selecionando a opção '200'...")
            xpath_opcao_200 = (
                f"{xpath_controle_paginacao}/teleport/ul/li[5]"
            )
            opcoes_200 = page.locator(f"xpath={xpath_opcao_200}")
            if opcoes_200.count() == 0:
                opcoes_200 = page.locator(
                    "[role='option']:visible, [role='menuitem']:visible, "
                    "li:visible, button:visible, div:visible"
                ).filter(has_text=re.compile(r"^\s*200\s*$"))
            clicou_200 = False
            for indice in range(opcoes_200.count() - 1, -1, -1):
                candidato = opcoes_200.nth(indice)
                if candidato.is_visible() and candidato.is_enabled():
                    candidato.click(force=True)
                    clicou_200 = True
                    break

            if not clicou_200:
                clicou_200 = page.evaluate(
                    """
                    () => {
                        const visivel = elemento => {
                            const estilo = getComputedStyle(elemento);
                            const caixa = elemento.getBoundingClientRect();
                            return estilo.display !== 'none'
                                && estilo.visibility !== 'hidden'
                                && caixa.width > 0 && caixa.height > 0;
                        };
                        const elementos = Array.from(document.querySelectorAll(
                            '[role="option"], [role="menuitem"], li, button, div, span'
                        ));
                        const texto = elementos.find(elemento =>
                            visivel(elemento)
                            && (elemento.innerText || '').trim() === '200'
                        );
                        if (!texto) return false;
                        const clicavel = texto.closest(
                            '[role="option"], [role="menuitem"], li, button'
                        ) || texto;
                        clicavel.click();
                        return true;
                    }
                    """
                )

            if not clicou_200:
                raise RuntimeError(
                    "Opção '200' não encontrada após abrir o seletor '50'"
                )
    
            print("  └─ ✅ Paginação alterada para 200 itens com sucesso!")
            aguardar_interface_pronta(page)
            page.locator("table:visible").first.wait_for(state="visible", timeout=15000)
            page.evaluate("window.scrollTo(0, 0)")
            return True
    except Exception as e:
            print(f"  └─ ⚠️ Erro ao alterar a paginação para 200: {e}")
            return False


def extrair_dados_linha(texto_linha):
    """Extrai CNPJ e nome da empresa a partir do texto de uma linha da tabela."""
    partes = [p.strip() for p in texto_linha.split("\n") if p.strip()]
    cnpj = None
    nome = None
    for parte in partes:
        cnpj_encontrado = extrair_cnpj(parte)
        if cnpj_encontrado:
            cnpj = cnpj_encontrado
            continue
        if not re.search(r'\d{2}/\d{2}/\d{4}', parte) and \
           not re.search(r'(Certificado|Vencido|Válido|Status)', parte, re.IGNORECASE) and \
           len(parte) > 3 and not parte.isdigit() and len(parte) < 100:
            if not nome:
                nome = parte
    return cnpj, nome


def localizar_linha_por_cnpj(page, cnpj, timeout=15000):
    """Retorna a linha visível cujo texto contém o CNPJ, com ou sem máscara."""
    cnpj_esperado = re.sub(r"\D", "", cnpj or "")
    if not cnpj_esperado:
        return None

    limite = time.monotonic() + timeout / 1000
    while time.monotonic() < limite:
        try:
            tabela = page.locator("table:visible").first
            tabela.wait_for(state="visible", timeout=1000)
            linhas = tabela.locator("tbody tr")

            for indice in range(linhas.count()):
                linha = linhas.nth(indice)
                if not linha.is_visible():
                    continue
                texto_normalizado = re.sub(r"\D", "", linha.inner_text())
                if cnpj_esperado in texto_normalizado:
                    return linha
        except Exception:
            # A tabela da SPA pode ser substituída durante o rerender.
            pass
        page.wait_for_timeout(300)

    return None


def forcar_fechamento_modais(page):
    """Fecha qualquer modal/drawer aberto para não atrapalhar a interação."""
    try:
        voltar_para_tabela_empresas(page, timeout=5000)
    except Exception:
        pass


def voltar_para_tabela_empresas(page, timeout=15000):
    """Fecha os modais por controles reais e confirma o retorno à tabela."""
    limite = time.monotonic() + timeout / 1000
    seletor_modal = (
        "[role='dialog']:visible, div[class*='modal']:visible, "
        "div[class*='drawer']:visible, div.su-modal:visible"
    )

    while time.monotonic() < limite:
        modais = page.locator(seletor_modal)
        if modais.count() == 0:
            try:
                page.locator("table:visible").first.wait_for(
                    state="visible", timeout=1000
                )
                return True
            except Exception:
                page.wait_for_timeout(250)
                continue

        modal = modais.last
        clicou = False

        seletores_fechar = (
            "button[aria-label*='fechar' i]",
            "button[title*='fechar' i]",
            "button[class*='close' i]",
        )
        for seletor in seletores_fechar:
            botoes = modal.locator(seletor)
            for indice in range(botoes.count() - 1, -1, -1):
                botao = botoes.nth(indice)
                if botao.is_visible():
                    botao.click(force=True)
                    clicou = True
                    break
            if clicou:
                break

        if not clicou:
            for texto in ("Cancelar", "Fechar", "Voltar", "Descartar", "Sim"):
                botoes = modal.get_by_role("button", name=texto, exact=True)
                for indice in range(botoes.count() - 1, -1, -1):
                    botao = botoes.nth(indice)
                    if botao.is_visible():
                        botao.click(force=True)
                        clicou = True
                        break
                if clicou:
                    break

        if not clicou:
            page.keyboard.press("Escape")

        page.wait_for_timeout(400)

    return False


def abrir_edicao_empresa(page, linha):
    """Abre a edição da empresa representada pela linha da tabela."""
    print("  Abrindo edição da empresa...")

    # O modal da versão atual da SIEG não possui input com name/id contendo
    # "nome". A confirmação correta é o título visível "Editar CNPJ/CPF".
    titulo_edicao = page.get_by_text("Editar CNPJ/CPF", exact=True)

    try:
        print("  └─ Tentando clique duplo na linha...")
        linha.scroll_into_view_if_needed()
        linha.dblclick()
        titulo_edicao.wait_for(state="visible", timeout=5000)
        print("  └─ ✅ Edição aberta via clique duplo")
        return True
    except Exception as e:
        # Às vezes o modal abriu, mas a animação fez o wait expirar.
        if titulo_edicao.count() and titulo_edicao.last.is_visible():
            print("  └─ ✅ Edição aberta via clique duplo")
            return True
        print(f"  └─ Clique duplo não abriu a edição: {e}")

    # Estratégia 2: menu de opções da linha.
    try:
        print("  └─ Tentando abrir menu de opções...")
        botoes = linha.locator("td:last-child button")
        btn_opcoes = None
        for i in range(botoes.count()):
            candidato = botoes.nth(i)
            if candidato.is_visible():
                btn_opcoes = candidato
                break

        if btn_opcoes is None:
            raise RuntimeError("botão de opções da linha não encontrado")

        btn_opcoes.scroll_into_view_if_needed()
        btn_opcoes.click()
        print("  └─ Menu de opções aberto")

        item_editar = page.get_by_text("Editar cadastro", exact=True)
        item_visivel = None
        for i in range(item_editar.count()):
            candidato = item_editar.nth(i)
            if candidato.is_visible():
                item_visivel = candidato
                break

        if item_visivel is None:
            raise RuntimeError("opção 'Editar cadastro' não encontrada no menu")

        item_visivel.click()
        titulo_edicao.last.wait_for(state="visible", timeout=10000)
        print("  └─ ✅ 'Editar cadastro' aberto")
        return True

    except Exception as e:
        print(f"  └─ Erro no menu de opções: {e}")
        print("  └─ ❌ Nenhuma estratégia funcionou para abrir a edição")
        return False


def clicar_botao_atualizar_certificado(page):
    """Localiza e clica no ícone de atualização (setinhas azuis) dentro do modal."""
    print("  Clicando no ícone de atualização do certificado...")
    time.sleep(1.5)

    # Caminho estrutural confirmado no modal atual: botão com as setas azuis
    # ao lado do estado "Vencido". Esta é a primeira estratégia para impedir
    # que outro botão pequeno do modal seja acionado por engano.
    botao_confirmado = page.locator(
        "xpath=/html/body/div[5]/div/div[2]/section[2]/section/"
        "div/div[2]/div/div[2]/div[1]/div/button"
    )
    try:
        botao_confirmado.wait_for(state="visible", timeout=10000)
        botao_confirmado.scroll_into_view_if_needed()
        botao_confirmado.click(force=True)
        print("  ✅ Ícone de atualização clicado")
        return True
    except Exception as erro_xpath:
        print(f"  ⚠️ Caminho principal do botão indisponível: {erro_xpath}")

    # Alternativa sem índice fixo, caso a página mude div[5] novamente.
    clicado = page.evaluate('''
        () => {
            const modal = document.querySelector(
                'div[class*="modal"]:not([style*="display: none"])'
            );
            const container = modal || document.body;
            const spans = Array.from(container.querySelectorAll('span, div'));
            const tagVencido = spans.find(
                el => el.textContent?.trim().toUpperCase() === 'VENCIDO'
            );
            if (tagVencido) {
                const parent = tagVencido.closest('div');
                const btn = parent?.querySelector('button');
                if (btn) { btn.click(); return true; }
            }
            const buttons = Array.from(container.querySelectorAll('button'));
            const btnSetas = buttons.find(b => {
                const rect = b.getBoundingClientRect();
                const temIcone = b.querySelector('svg') || b.querySelector('i');
                const naoTexto = !b.textContent.includes('Cancelar')
                    && !b.textContent.includes('Salvar');
                return rect.width > 0 && rect.width < 60 && temIcone && naoTexto;
            });
            if (btnSetas) { btnSetas.click(); return true; }
            return false;
        }
    ''')
    if clicado:
        print("  ✅ Ícone de atualização clicado")
    else:
        print("  ⚠️ Ícone não encontrado")
    return clicado


def _clicar_botao_atualizar_certificado_por_xpath(page):
    """Localiza e clica no botão de atualização dentro do modal."""
    print("  Clicando no botão de atualização do certificado...")
    xpath_container_certificado = (
        "/html/body/div[6]/div/div[2]/section[2]/section/div/div[2]"
    )
    seletor_atualizar = (
        f"xpath={xpath_container_certificado}"
        "//*[normalize-space(.)='VENCIDO']/following::button[1]"
    )
    botao_atualizar = page.locator(seletor_atualizar)
    clicado = False
    try:
        botao_atualizar.wait_for(state="visible", timeout=10000)
        botao_atualizar.scroll_into_view_if_needed()
        botao_atualizar.click(force=True)
        clicado = True
    except Exception:
        pass

    if not clicado:
        # XPath estrutural informado, usado se o texto VENCIDO estiver em um
        # componente que não exponha seu conteúdo ao XPath.
        botao_estrutural = page.locator(
            f"xpath={xpath_container_certificado}/div/div[2]/div[1]/div/button"
        )
        try:
            botao_estrutural.wait_for(state="visible", timeout=3000)
            botao_estrutural.scroll_into_view_if_needed()
            botao_estrutural.click(force=True)
            clicado = True
        except Exception:
            pass

    if not clicado:
        # Última tentativa restrita ao contêiner: sobe a partir de VENCIDO até
        # encontrar o bloco que também contém um botão e clica nesse botão.
        clicado = page.locator(f"xpath={xpath_container_certificado}").evaluate(
            """
            container => {
                const visivel = elemento => {
                    const estilo = getComputedStyle(elemento);
                    const caixa = elemento.getBoundingClientRect();
                    return estilo.display !== 'none'
                        && estilo.visibility !== 'hidden'
                        && caixa.width > 0 && caixa.height > 0;
                };
                const vencido = Array.from(container.querySelectorAll('*')).find(
                    elemento => elemento.textContent?.trim().toUpperCase() === 'VENCIDO'
                );
                let bloco = vencido?.parentElement;
                while (bloco && bloco !== container.parentElement) {
                    const botao = Array.from(bloco.querySelectorAll('button')).find(visivel);
                    if (botao) {
                        botao.click();
                        return true;
                    }
                    bloco = bloco.parentElement;
                }
                return false;
            }
            """
        )

    if not clicado:
        clicado = page.evaluate('''
        () => {
            const gatilhoTooltip = Array.from(document.querySelectorAll('button, [role="button"]'))
                .find(elemento => {
                    const atributos = [
                        elemento.getAttribute('aria-label'),
                        elemento.getAttribute('title'),
                        elemento.getAttribute('data-tooltip'),
                        elemento.getAttribute('data-tooltip-content')
                    ];
                    return atributos.some(valor => valor?.toLowerCase().includes('atualizar certificado'));
                });
            if (gatilhoTooltip) {
                gatilhoTooltip.click();
                return true;
            }
            const modais = Array.from(document.querySelectorAll('div[class*="modal"], div[class*="drawer"]'));
            const modal = modais.reverse().find(elemento => {
                const estilo = getComputedStyle(elemento);
                const caixa = elemento.getBoundingClientRect();
                return estilo.display !== 'none'
                    && estilo.visibility !== 'hidden'
                    && caixa.width > 0
                    && caixa.height > 0;
            });
            const container = modal || document.body;
            const spans = Array.from(container.querySelectorAll('span, div'));
            const tagVencido = spans.find(el => el.textContent?.trim().toUpperCase() === 'VENCIDO');
            if (tagVencido) {
                const parent = tagVencido.closest('div');
                const btn = parent?.querySelector('button');
                if (btn) { btn.click(); return true; }
            }
            const buttons = Array.from(container.querySelectorAll('button'));
            const btnSetas = buttons.find(b => {
                const rect = b.getBoundingClientRect();
                const temIcone = b.querySelector('svg') || b.querySelector('i');
                const naoTexto = !b.textContent.includes('Cancelar') && !b.textContent.includes('Salvar');
                return rect.width > 0 && rect.width < 60 && temIcone && naoTexto;
            });
            if (btnSetas) { btnSetas.click(); return true; }
            return false;
        }
        ''')
    if clicado:
        page.locator("input[type='file']").first.wait_for(state="attached", timeout=30000)
        print("  ✅ Botão de atualização clicado")
    else:
        print("  ⚠️ Botão de atualização não encontrado")
    return clicado


def preencher_uf_ce(page):
    """Seleciona CE no campo Estado do modal de edição da SIEG."""
    print("  └─ Preenchendo campo Estado/UF...")
    try:
        rotulo_estado = page.locator("label:visible").filter(
            has_text=re.compile(r"^\s*Estado\s*:\s*", re.IGNORECASE)
        )
        rotulo_estado.first.wait_for(state="visible", timeout=10000)

        # Quando o cadastro já possui uma UF, o componente mostra a sigla no
        # lugar do placeholder "UF". Nesse caso não é necessário abri-lo.
        conteudo_estado = rotulo_estado.first.evaluate(
            """
            rotulo => {
                const valores = Array.from(
                    rotulo.querySelectorAll('input, select, [role="combobox"]')
                ).flatMap(elemento => [
                    elemento.value,
                    elemento.getAttribute('value'),
                    elemento.innerText,
                    elemento.textContent
                ]);
                valores.push(rotulo.innerText, rotulo.textContent);
                return valores.filter(Boolean).join(' ');
            }
            """
        )
        ufs = {
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
            "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
            "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        }
        uf_preenchida = next(
            (
                trecho
                for trecho in re.findall(r"\b[A-Z]{2}\b", conteudo_estado.upper())
                if trecho in ufs
            ),
            None,
        )
        if uf_preenchida:
            print(f"  └─ ✓ Estado/UF já preenchido com {uf_preenchida}. Pulando.")
            return True

        campo_estado = rotulo_estado.first.get_by_text("UF", exact=True)
        campo_estado.wait_for(state="visible", timeout=5000)
        campo_estado.scroll_into_view_if_needed()

        # O componente escuta eventos de ponteiro no nó/ancestral, não apenas
        # um clique físico por coordenadas.
        campo_estado.click(force=True)
        campo_estado.evaluate(
            """
            elemento => {
                for (const tipo of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
                    elemento.dispatchEvent(new MouseEvent(tipo, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                }
            }
            """
        )
        print("  └─ Menu 'Estado' clicado.")
        time.sleep(0.7)

        selecionou = False
        opcoes = page.get_by_text("CE", exact=True)
        for i in range(opcoes.count() - 1, -1, -1):
            opcao = opcoes.nth(i)
            if opcao.is_visible():
                opcao.click(force=True)
                selecionou = True
                break

        if not selecionou:
            page.keyboard.type("CE", delay=150)
            time.sleep(0.5)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")

        page.keyboard.press("Tab")
        expect(rotulo_estado.first).to_contain_text("CE", timeout=3000)

        print("  └─ ✅ UF 'CE' selecionada e confirmada!")
        return True

    except Exception as e:
        print(f"  └─ ⚠️ Erro ao selecionar o Estado/UF: {e}")
        try:
            page.screenshot(path="registros/erros/erro_selecao_uf.png", full_page=True)
        except Exception:
            pass
        return False


def confirmar_linha_empresa(linha, cnpj, nome_empresa):
    """Confirma que a linha localizada contém o CNPJ que será processado."""
    try:
        texto_linha = linha.inner_text()
        cnpj_linha = re.sub(r"\D", "", texto_linha)
        cnpj_esperado = re.sub(r"\D", "", cnpj)
        if cnpj_esperado and cnpj_esperado in cnpj_linha:
            print(f"  ✅ Linha confirmada para o CNPJ {cnpj_esperado}")
            return True
        print(
            f"  ❌ Segurança: a linha clicada não corresponde ao CNPJ "
            f"{cnpj_esperado} ({nome_empresa})"
        )
        return False
    except Exception as erro:
        print(f"  ❌ Não foi possível confirmar a linha da empresa: {erro}")
        return False


def aguardar_validacao_senha_certificado(page, timeout_ms=30000):
    """Espera uma mensagem explícita de sucesso ou erro após informar a senha."""
    seletores = (
        "[role='alert']:visible, [class*='toast']:visible, "
        "[class*='notification']:visible, [class*='message']:visible, "
        "div[class*='modal']:visible, div[class*='drawer']:visible"
    )

    print("  ⏳ Aguardando a confirmação da senha do certificado...")
    try:
        resultado = page.wait_for_function(
            r"""
            (seletor) => {
                const erro = /(senha.{0,40}(incorret|inválid|invalid|errad)|certificado.{0,50}(inválid|invalid|erro|falha)|(erro|falha).{0,50}(senha|certificado))/i;
                const sucesso = /(senha.{0,40}(corret|válid|valid)|certificado.{0,50}(carregad|importad|atualizad|válid|valid|sucesso)|sucesso.{0,50}certificado)/i;
                for (const elemento of document.querySelectorAll(seletor)) {
                    const estilo = getComputedStyle(elemento);
                    const caixa = elemento.getBoundingClientRect();
                    if (estilo.display === 'none' || estilo.visibility === 'hidden'
                        || caixa.width === 0 || caixa.height === 0) continue;
                    const texto = (elemento.innerText || '').replace(/\s+/g, ' ').trim();
                    const erroEncontrado = texto.match(erro);
                    if (erroEncontrado) return { sucesso: false, mensagem: erroEncontrado[0] };
                    const sucessoEncontrado = texto.match(sucesso);
                    if (sucessoEncontrado) return { sucesso: true, mensagem: sucessoEncontrado[0] };
                }
                return false;
            }
            """,
            arg=seletores.replace(":visible", ""),
            timeout=timeout_ms,
        ).json_value()
        return resultado["sucesso"], resultado["mensagem"]
    except Exception:
        return False, f"nenhuma mensagem de sucesso ou erro apareceu em {timeout_ms // 1000}s"
