import re
from playwright.sync_api import expect
from .identidade import normalizar_texto

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
            if not seletor.startswith((".", "#", "input", "button", "[", "div", "xpath", "//")):
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


_NOMES_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}


def preencher_uf_se_necessario(page, uf):
    """Preenche a UF configurada somente quando o campo estiver vazio."""
    uf = (uf or "").strip().upper()
    if uf not in _NOMES_UF:
        raise ValueError(f"UF inválida para preenchimento no SIEG: {uf or '<vazia>'}")
    seletores = (
        "select[name*='uf' i], select[id*='uf' i], "
        "input[name*='uf' i], input[id*='uf' i], "
        "[role='combobox'][name*='uf' i], [role='combobox'][id*='uf' i], "
        "input[placeholder*='UF' i], [aria-label*='UF' i]"
    )
    campo_uf = None

    # A tela pode montar o formulario alguns segundos depois de abrir a edicao.
    xpath_label_estado = (
        "xpath=/html/body/div/div/div[2]/section[2]/section/div[1]/"
        "fieldset/label[4]"
    )
    for _ in range(10):
        label_estado = page.locator(xpath_label_estado).filter(visible=True).last
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

    print(f"PASSO 8/9: UF vazia. Preenchendo como '{uf}'...")
    if tag == "select":
        try:
            campo_uf.select_option(uf)
        except Exception:
            opcoes = campo_uf.locator("option").all()
            valores_esperados = {
                normalizar_texto(uf), normalizar_texto(_NOMES_UF[uf])
            }
            opcao = next(
                item for item in opcoes
                if normalizar_texto(item.inner_text()) in valores_esperados
            )
            campo_uf.select_option(value=opcao.get_attribute("value"))
        return

    campo_uf.click()
    if tag in ("input", "textarea"):
        campo_uf.fill(uf)
    nome_uf = re.compile(
        rf"^\s*({re.escape(uf)}|{re.escape(_NOMES_UF[uf])})\s*$",
        re.IGNORECASE,
    )
    opcao_uf = page.get_by_role("option", name=nome_uf).last
    try:
        opcao_uf.wait_for(state="visible", timeout=3000)
        opcao_uf.click()
    except Exception:
        if tag not in ("input", "textarea"):
            campo_uf.evaluate("""elemento => {
                for (const tipo of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
                    elemento.dispatchEvent(new MouseEvent(tipo, {bubbles: true, cancelable: true, view: window}));
                }
            }""")
        opcoes = page.get_by_text(nome_uf)
        for indice in range(opcoes.count() - 1, -1, -1):
            if opcoes.nth(indice).is_visible():
                opcoes.nth(indice).click(force=True)
                break
        else:
            page.keyboard.type(uf, delay=150)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    if tag in ("input", "textarea"):
        expect(campo_uf).to_have_value(uf, timeout=3000)
    else:
        expect(campo_uf).to_contain_text(uf, timeout=3000)


def preencher_uf(page, uf):
    """Contrato booleano usado pela automação de certificados vencidos."""
    try:
        preencher_uf_se_necessario(page, uf)
        return True
    except Exception as erro:
        print(f"Não foi possível preencher Estado/UF: {erro}")
        return False
