"""Seletores relativos ao diálogo ativo, sem fallback para o body."""

import re
import time


# Classes de contêiner: não incluir fragmentos como modal-footer/backdrop,
# que podem ser selecionados depois do formulário e excluir seus campos.
SELETOR_MODAL = (
    "[role='dialog']:visible, [aria-modal='true']:visible, dialog[open]:visible, "
    ".su-modal:visible, .modal:visible, .drawer:visible, .su-drawer:visible"
)


def modal_visivel(page, timeout=15000):
    limite = time.monotonic() + timeout / 1000
    while time.monotonic() < limite:
        modais = localizar_modais(page)
        if modais.count():
            return modais.last
        page.wait_for_timeout(100)
    raise TimeoutError(
        "A janela de edição/certificado não apareceu. "
        "Verifique se a edição abriu e se a etapa anterior avançou."
    )


def localizar_modais(page):
    """Inclui painéis posicionados sem role ou classe de biblioteca."""
    modais = page.locator(SELETOR_MODAL)
    # O SIEG também pode renderizar painéis com classes utilitárias.
    # Exigir ação do assistente e excluir contêineres da tabela evita
    # promover a página inteira a diálogo.
    paineis = page.locator("div:visible, section:visible, aside:visible").filter(
        has=page.get_by_role("button", name=re.compile(
            r"^(Salvar e continuar|Concluir|Confirmar e finalizar|"
            r"Cadastrar certificado A1|Atualizar certificado|Cancelar|Fechar)$",
            re.IGNORECASE,
        )).filter(visible=True)
    ).filter(has_not=page.locator("table"))
    indices = paineis.evaluate_all("""elementos => elementos.map((el, i) =>
        ['fixed', 'absolute'].includes(getComputedStyle(el).position) ? i : -1
    ).filter(i => i >= 0)""")
    for indice in indices:
        modais = modais.or_(paineis.nth(indice))
    return modais


def botao_modal(page, nome, timeout=15000):
    return modal_visivel(page, timeout).get_by_role("button", name=nome, exact=True)


def campo_upload_modal(page, tipo, timeout=15000):
    modal = modal_visivel(page, timeout)
    campos = modal.locator(f"input[type='{tipo}']")
    nome = re.compile("senha" if tipo == "password" else "certificado|arquivo", re.IGNORECASE)
    rotulados = modal.get_by_label(nome).and_(campos)
    return rotulados if rotulados.count() else campos


def botao_atualizar_certificado(page, timeout=15000):
    modal = modal_visivel(page, timeout)
    nome = re.compile(r"(?:atualizar|renovar)(?:\s+(?:o\s+)?certificado)?", re.IGNORECASE)
    botoes = modal.get_by_role("button", name=nome)
    # Ícones podem anunciar sua ação apenas em title ou tooltip.
    atributos = modal.locator(
        "button[title*='atualizar' i], button[title*='renovar' i], "
        "button[data-tooltip*='atualizar certificado' i], "
        "button[data-tooltip-content*='atualizar certificado' i]"
    )
    identificados = botoes.or_(atributos).filter(visible=True)
    if identificados.count():
        return identificados
    # Botão de ícone cujo caminho foi identificado na tela do SIEG.
    # Preserva a estrutura interna, sem depender do índice div[6] no body.
    estrutural = modal.locator(
        "xpath=.//section[2]/section/div/div[2]/div/div[2]/div[1]/div/button"
    )
    return identificados.or_(estrutural).filter(visible=True)
