import os
from playwright.sync_api import sync_playwright

from config import ARQUIVO_ENV, DRIVE_ROOT_FOLDER_ID
from drive_service import (
    autenticar_drive,
    criar_indice_pastas_drive,
    iterar_certificados_candidatos_drive,
)
from persistencia import (
    adicionar_falha,
    carregar_cnpjs_processados,
    gerar_resumo_execucao,
    registrar_cnpj_processado,
)
from sieg_service import (
    aguardar_validacao_senha_certificado,
    alterar_paginacao_para_200,
    aplicar_filtro_vencidos,
    abrir_edicao_empresa,
    aguardar_interface_pronta,
    clicar_botao_atualizar_certificado,
    clicar_com_rolagem,
    confirmar_linha_empresa,
    extrair_dados_linha,
    forcar_fechamento_modais,
    localizar_linha_por_cnpj,
    preencher_uf_ce,
    realizar_login_sieg,
    voltar_para_tabela_empresas,
)
from utilitarios import extrair_cnpj, normalizar_texto


def garantir_input_ativo(page, xpath, descricao, xpath_alternativo=None):
    """Marca um checkbox/radio apenas quando ele ainda não estiver selecionado."""
    campo = page.locator(f"xpath={xpath}")
    try:
        campo.wait_for(state="visible", timeout=10000)
    except Exception:
        if not xpath_alternativo:
            raise
        campo = page.locator(f"xpath={xpath_alternativo}").last
        campo.wait_for(state="visible", timeout=5000)
    if not campo.is_checked():
        campo.check(force=True)
        print(f"  ✅ Opção ativada: {descricao}")
    else:
        print(f"  ✓ Opção já estava ativa: {descricao}")


def clicar_salvar_e_continuar(page, etapa):
    """Clica no botão exato da etapa atual e aguarda a interface avançar."""
    botao = page.get_by_role(
        "button", name="Salvar e continuar", exact=True
    ).last
    botao.wait_for(state="visible", timeout=15000)
    botao.scroll_into_view_if_needed()
    print(f"  Salvando e continuando ({etapa})...")
    botao.click()
    aguardar_interface_pronta(page, timeout=30000)


def preparar_tela_upload_certificado(page, cnpj, nome_empresa):
    """Abre com segurança a tela de upload para uma nova tentativa."""
    linha = localizar_linha_por_cnpj(page, cnpj)
    if linha is None:
        raise RuntimeError("Linha não encontrada na tabela")

    if not confirmar_linha_empresa(linha, cnpj, nome_empresa):
        raise RuntimeError(
            "A linha localizada não corresponde ao CNPJ esperado"
        )

    if not abrir_edicao_empresa(page, linha):
        raise RuntimeError("Não foi possível abrir a edição da empresa")

    if not preencher_uf_ce(page):
        raise RuntimeError("Não foi possível selecionar a UF CE")

    botao_salvar = page.locator("button:visible").filter(
        has_text="Salvar e continuar"
    ).last
    botao_salvar.wait_for(state="visible", timeout=10000)
    botao_salvar.scroll_into_view_if_needed()
    botao_salvar.click()
    aguardar_interface_pronta(page)

    garantir_input_ativo(
        page,
        "/html/body/div[5]/div/div[2]/section[2]/section/div/label/input",
        "atualização do certificado",
        "/html/body/div[.//text()[normalize-space()='Vencido' or "
        "normalize-space()='VENCIDO']]"
        "//section[2]/section/div/label/input",
    )

    if not clicar_botao_atualizar_certificado(page):
        raise RuntimeError(
            "Botão de atualização do certificado não encontrado"
        )


def executar_automacao_sieg():
    """Orquestra todo o fluxo de automação."""
    email_sieg = os.getenv("SIEG_EMAIL")
    senha_sieg = os.getenv("SIEG_SENHA")
    if not email_sieg or not senha_sieg:
        raise RuntimeError(f"Preencha SIEG_EMAIL e SIEG_SENHA no arquivo {ARQUIVO_ENV}")

    # Autentica no Google Drive
    service = autenticar_drive()
    print("✅ Autenticado no Google Drive com sucesso!")
    print("📁 Criando índice das pastas do Google Drive...")
    indice_drive = criar_indice_pastas_drive(service, DRIVE_ROOT_FOLDER_ID)
    print(f"✅ {indice_drive['total']} pasta(s) indexada(s) em uma única consulta.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        page.set_default_navigation_timeout(100000)

        print("=" * 60)
        print("🚀 INICIANDO AUTOMAÇÃO SIEG")
        print("=" * 60)

        # 1. Acessar e logar
        # O Hub pode continuar carregando recursos por bastante tempo. Para a
        # navegação inicial, basta o servidor responder; os elementos da tela
        # são aguardados explicitamente nas etapas seguintes.
        page.goto(
            "https://hub.sieg.com/",
            wait_until="commit",
            timeout=100000,
        )
        if not realizar_login_sieg(page, email_sieg, senha_sieg):
            browser.close()
            raise RuntimeError("Não foi possível concluir o login no SIEG")
        
        print("⏳ Aguardando carregamento completo da página...")
        try:
        # Espera até que o elemento "Todos os serviços" esteja visível (máx 30s)
            page.wait_for_selector("text=Todos os serviços", timeout=100000)
            print("✅ Página carregada com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao carregar página: {e}")
            page.wait_for_load_state("domcontentloaded")

        # 2. Navegar até Gerenciar CNPJs
        clicar_com_rolagem(page, "Todos os serviços")
        page.get_by_text("Gerenciar CNPJs", exact=False).first.wait_for(state="visible", timeout=30000)
        clicar_com_rolagem(page, "Gerenciar CNPJs")
        
        print("⏳ Aguardando carregamento completo da página...")
        try:
        # Espera até que o elemento "Todos os serviços" esteja visível (máx 30s)
            page.wait_for_selector("text=Controle de Cadastros", timeout=100000)
            print("✅ Página carregada com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao carregar página: {e}")
            page.wait_for_load_state("domcontentloaded")

        # 3. Aplicar filtro de vencidos
        aplicar_filtro_vencidos(page)

        # 4. Paginação para 200
        if not alterar_paginacao_para_200(page):
            raise RuntimeError(
                "Não foi possível exibir todas as empresas na tabela"
            )
        page.locator("table:visible").first.wait_for(state="visible", timeout=15000)

        # 5. Capturar lista de empresas
        print("📋 Capturando lista de empresas...")
        linhas = page.locator("table:visible").first.locator("tbody tr").all()
        dados = []
        for linha in linhas:
            texto = linha.inner_text()
            cnpj, nome = extrair_dados_linha(texto)
            if cnpj:
                dados.append({"cnpj": cnpj, "nome": nome})

        total = len(dados)
        if total == 0:
            print("❌ Nenhuma empresa encontrada.")
            browser.close()
            return

        print(f"📊 Total de empresas: {total}")
        cnpjs_listados_sieg = {item["cnpj"] for item in dados}
        nomes_listados_sieg = {
            normalizar_texto(item["nome"])
            for item in dados
            if item.get("nome")
        }
        quantidade_certas = 0
        pastas_verificadas = set()
        for nome_normalizado, pasta in indice_drive["por_nome"]:
            pasta_id = pasta.get("id")
            if pasta_id in pastas_verificadas:
                continue
            pastas_verificadas.add(pasta_id)

            nome_pasta = pasta.get("name", "")
            cnpj_pasta = extrair_cnpj(nome_pasta)
            esta_no_sieg = (
                cnpj_pasta in cnpjs_listados_sieg
                if cnpj_pasta
                else any(
                    nome_sieg in nome_normalizado
                    or nome_normalizado in nome_sieg
                    for nome_sieg in nomes_listados_sieg
                )
            )
            if not esta_no_sieg:
                quantidade_certas += 1
        print(f"✅ Empresas não listadas no SIEG: {quantidade_certas}")

        # 6. Processar cada empresa
        sucessos = 0
        falhas = 0
        ignorados = 0
        empresas_sucesso = []
        falhas_detalhes = []
        cnpjs_processados = carregar_cnpjs_processados()
        if cnpjs_processados:
            print(f"♻️ {len(cnpjs_processados)} CNPJ(s) já concluído(s) hoje serão ignorados.")
        for idx, item in enumerate(dados):
            cnpj = item["cnpj"]
            nome_empresa = item["nome"]
            print(f"\n▶️ Empresa {idx+1}/{total}: {cnpj} - {nome_empresa}")

            if cnpj in cnpjs_processados:
                print("⏭️ Empresa já processada com sucesso hoje. Pulando.")
                ignorados += 1
                continue

            # Fecha modais pendentes
            forcar_fechamento_modais(page)

            try:
                # 6a–6g. Testar, em ordem, todos os certificados vindos de
                # pastas com nome exato/equivalente ou similaridade >= 85%.
                certificado_aceito = None
                rejeicoes = []
                total_tentativas = 0
                candidatos = iterar_certificados_candidatos_drive(
                    nome_empresa,
                    service,
                    DRIVE_ROOT_FOLDER_ID,
                    indice_drive,
                )

                for candidato in candidatos:
                    total_tentativas += 1
                    print(
                        f"  🧪 Tentativa {total_tentativas}: "
                        f"{candidato['pasta_nome']} / "
                        f"{candidato['arquivo_nome']} "
                        f"({candidato['similaridade']:.0%})"
                    )
                    preparar_tela_upload_certificado(
                        page, cnpj, nome_empresa
                    )

                    campo_file = page.locator(
                        "[role='dialog']:visible input[type='file'], "
                        "div[class*='modal']:visible input[type='file'], "
                        "div[class*='drawer']:visible input[type='file']"
                    ).last
                    campo_file.wait_for(state="attached", timeout=15000)
                    campo_file.set_input_files({
                        'name': candidato['arquivo_nome'],
                        'mimeType': 'application/x-pkcs12',
                        'buffer': candidato['pfx_bytes'],
                    })

                    campo_pass = page.locator(
                        "[role='dialog']:visible input[type='password']:visible, "
                        "div[class*='modal']:visible input[type='password']:visible, "
                        "div[class*='drawer']:visible input[type='password']:visible"
                    ).last
                    campo_pass.wait_for(state="visible", timeout=15000)
                    campo_pass.fill(candidato['senha'])
                    campo_pass.dispatch_event("input")
                    senha_aceita, mensagem_validacao = (
                        aguardar_validacao_senha_certificado(page)
                    )
                    if senha_aceita:
                        print(
                            "  ✅ Senha confirmada pelo SIEG: "
                            f"{mensagem_validacao}"
                        )
                        try:
                            # A aceitação definitiva só ocorre quando o SIEG
                            # permite avançar para a etapa seguinte. É nesse
                            # avanço que ele também pode rejeitar o titular.
                            clicar_salvar_e_continuar(page, "certificado")
                            garantir_input_ativo(
                                page,
                                "/html/body/div[6]/div/div[2]/section[2]/"
                                "div/div[3]/div[2]/div[1]/div[2]/input",
                                "primeira opção da etapa",
                            )
                            garantir_input_ativo(
                                page,
                                "/html/body/div[6]/div/div[2]/section[2]/"
                                "div/div[3]/div[2]/div[2]/div[2]/"
                                "label[1]/input",
                                "segunda opção da etapa",
                            )
                            certificado_aceito = candidato
                            print(
                                "  ✅ Certificado aceito e próxima etapa aberta."
                            )
                            break
                        except Exception as erro_avanco:
                            mensagem_validacao = (
                                "o SIEG não permitiu avançar após o upload: "
                                f"{erro_avanco}"
                            )

                    motivo_rejeicao = (
                        f"{candidato['pasta_nome']}: {mensagem_validacao}"
                    )
                    rejeicoes.append(motivo_rejeicao)
                    print(
                        "  ⚠️ Candidato rejeitado pelo SIEG; "
                        "voltando para testar o próximo."
                    )
                    if not voltar_para_tabela_empresas(page):
                        raise RuntimeError(
                            "O certificado foi rejeitado, mas não foi possível "
                            "voltar com segurança à tabela"
                        )

                if certificado_aceito is None:
                    if total_tentativas == 0:
                        motivo = (
                            "Nenhum certificado válido encontrado em pasta "
                            "com similaridade mínima de 85%"
                        )
                    else:
                        motivo = (
                            f"SIEG rejeitou os {total_tentativas} "
                            "certificado(s) candidato(s): "
                            + " | ".join(rejeicoes)
                        )
                    print(f"❌ {motivo}. Pulando.")
                    adicionar_falha(
                        falhas_detalhes,
                        page,
                        cnpj,
                        nome_empresa,
                        motivo,
                    )
                    falhas += 1
                    continue

                # A etapa do certificado e as duas opções já foram confirmadas
                # dentro da tentativa vencedora. Restam duas etapas.
                clicar_salvar_e_continuar(page, "segunda etapa")
                clicar_salvar_e_continuar(page, "terceira etapa")

                # Confirma a opção final antes de concluir o assistente.
                garantir_input_ativo(
                    page,
                    "/html/body/div[6]/div/div[2]/section[2]/section/"
                    "div[2]/div/div/label[1]/input",
                    "opção final",
                )

                # "Concluir" pertence à etapa seguinte e só pode ser clicado
                # depois que todas as etapas anteriores forem salvas.
                botao_concluir = page.get_by_role(
                    "button", name="Concluir", exact=True
                ).last
                botao_concluir.wait_for(state="visible", timeout=30000)
                print("  Etapas salvas. Clicando em 'Concluir'...")
                botao_concluir.scroll_into_view_if_needed()
                botao_concluir.click()
                aguardar_interface_pronta(page)
                if not clicar_com_rolagem(page, "Confirmar e finalizar"):
                    raise RuntimeError("Não foi possível clicar em 'Confirmar e finalizar'")
                aguardar_interface_pronta(page, timeout=30000)
                page.locator("table:visible").first.wait_for(state="visible", timeout=30000)

                print(f"✅ Empresa {cnpj} processada com sucesso!")
                registrar_cnpj_processado(cnpj, nome_empresa)
                cnpjs_processados.add(cnpj)
                empresas_sucesso.append({"cnpj": cnpj, "nome": nome_empresa})
                sucessos += 1

            except Exception as err:
                print(f"❌ ERRO: {err}")
                adicionar_falha(falhas_detalhes, page, cnpj, nome_empresa, err)
                falhas += 1
            finally:
                forcar_fechamento_modais(page)

        # 7. Resumo final
        print("\n" + "=" * 60)
        print(f"📊 RESUMO: ✅ {sucessos} sucessos | ❌ {falhas} falhas")
        print("=" * 60)
        arquivo_resumo = gerar_resumo_execucao(
            sucessos,
            falhas_detalhes,
            ignorados,
            service,
            empresas_sucesso=empresas_sucesso,
            quantidade_certas=quantidade_certas,
        )

        print(
        f"📝 Resumo enviado ao Google Drive: "
        f"{arquivo_resumo['name']}")
        print(
        f"🔗 Link do relatório: "
        f"{arquivo_resumo.get('webViewLink', '')}"
            )

        browser.close()
