"""Seletores relativos ao diálogo ativo, sem índices ou fallback para o body."""

import re


def modal_visivel(page, timeout=15000):
    modal = page.locator("[role='dialog']:visible, [aria-modal='true']:visible, dialog[open]:visible").last
    modal.wait_for(state="visible", timeout=timeout)
    return modal


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
    return botoes.or_(atributos).filter(visible=True)
