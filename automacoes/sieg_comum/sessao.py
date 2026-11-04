import re

def realizar_login_sieg(page, email, senha):
    """Preenche e submete o formulário de login."""
    print("🔑 Realizando login...")
    try:
        destino = page.get_by_text(re.compile(r"Todos os servi[cç]os", re.IGNORECASE)).first
        if destino.is_visible():
            return True
        if not email or not senha:
            raise ValueError("Defina SIEG_EMAIL e SIEG_SENHA no arquivo .env.")
        campo_email = page.locator("input[type='email'], input[placeholder*='e-mail'], input[name*='email' i], input[id*='email' i]").first
        campo_email.wait_for(state="visible", timeout=60000)
        campo_email.fill(email)

        campo_senha = page.locator("input[type='password'], input[placeholder*='senha']").first
        campo_senha.fill(senha)

        btn_entrar = page.get_by_role("button", name=re.compile(r"entrar|login|acessar", re.IGNORECASE)).first
        if btn_entrar.is_visible():
            btn_entrar.click()
        else:
            page.keyboard.press("Enter")
        destino.wait_for(
            state="visible", timeout=100000
        )
        return True
    except Exception as e:
        print(f"❌ Falha no login: {e}")
        return False
