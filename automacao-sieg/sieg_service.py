import _bootstrap
from sieg_comum.modais import botao_atualizar_certificado
from sieg_comum.navegacao import (aguardar_interface_pronta, clicar_com_rolagem, abrir_edicao_empresa, preencher_uf)
from sieg_comum.sessao import realizar_login_sieg

import re
import time


from utilitarios import extrair_cnpj


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


class CertificadoRejeitadoError(RuntimeError):
    """O SIEG exibiu uma rejeição explícita do certificado ou de sua senha."""


def _script_validacao_certificado():
    """Detector compartilhado de mensagens; não comprova persistência do upload."""
    return r"""
        ({somente_erros = false} = {}) => {
            const seletor = '[role="alert"], [role="dialog"], [class*="toast"], '
                + '[class*="notification"], [class*="message"], '
                + 'div[class*="modal"], div[class*="drawer"]';
            const erro = /(senha.{0,40}(incorret|invalid|errad|nao confere)|certificado.{0,80}(invalid|incompativ|rejeitad|nao (pertence|corresponde|confere))|(titular|cnpj|cpf).{0,100}(diverg|diferent|incompativ|nao (correspond|pertenc|coincid|confere|e o mesmo))|(incompativel|divergente|diferente).{0,50}(titular|cnpj|cpf))/i;
            const sucesso = /(senha\s+(?:(?:do certificado|informada|digitada|esta|e|foi)\s+)*(correta|valida(?:da|do)?)\b|certificado\s+(?:(?:digital|foi|esta|e)\s+)*(carregado|importado|atualizado|valido)\b|sucesso.{0,50}certificado)/i;
            let confirmacao = null;
            for (const elemento of document.querySelectorAll(seletor)) {
                const estilo = getComputedStyle(elemento);
                const caixa = elemento.getBoundingClientRect();
                if (estilo.display === 'none' || estilo.visibility === 'hidden'
                    || caixa.width === 0 || caixa.height === 0) continue;
                const texto = (elemento.innerText || '').replace(/\s+/g, ' ').trim();
                const normalizado = texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
                const erroEncontrado = normalizado.match(erro);
                if (erroEncontrado) return {
                    sucesso: false,
                    mensagem: texto.slice(erroEncontrado.index, erroEncontrado.index + erroEncontrado[0].length)
                };
                if (!somente_erros && !confirmacao) {
                    const sucessoEncontrado = normalizado.match(sucesso);
                    if (sucessoEncontrado) confirmacao = {
                        sucesso: true,
                        mensagem: texto.slice(sucessoEncontrado.index, sucessoEncontrado.index + sucessoEncontrado[0].length)
                    };
                }
            }
            // Percorre todos os avisos antes de aceitar uma mensagem de senha válida.
            return confirmacao || false;
        }
    """


def obter_rejeicao_certificado(page):
    """Retorna somente rejeição explícita visível, nunca timeout ou vencimento."""
    resultado = page.evaluate(
        _script_validacao_certificado(), {"somente_erros": True}
    )
    return resultado["mensagem"] if resultado else None


def aguardar_validacao_senha_certificado(page, timeout_ms=30000):
    """Retorna (True/False/None, mensagem): aceita, rejeitada ou inconclusiva."""
    print("  ⏳ Aguardando a confirmação da senha do certificado...")
    try:
        resultado = page.wait_for_function(
            _script_validacao_certificado(),
            arg={"somente_erros": False},
            timeout=timeout_ms,
        ).json_value()
        return resultado["sucesso"], resultado["mensagem"]
    except Exception:
        return None, (
            "validação inconclusiva: não foi possível obter uma mensagem "
            f"explícita de sucesso ou rejeição em {timeout_ms / 1000:g}s"
        )


def clicar_botao_atualizar_certificado(page):
    """Aciona a atualizacao identificada pelo nome ou tooltip no dialogo ativo."""
    try:
        botao = botao_atualizar_certificado(page)
        botao.wait_for(state="visible", timeout=10000)
        botao.scroll_into_view_if_needed()
        botao.click()
        return True
    except Exception as erro:
        print(f"Botao de atualizar certificado indisponivel no dialogo ativo: {erro}")
        return False
