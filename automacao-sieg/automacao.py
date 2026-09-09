import os
import re
import time
from playwright.sync_api import sync_playwright

from config import (
    ARQUIVO_ENV, DRIVE_ROOT_FOLDER_ID, SIEG_SLOW_MO_MS, SIEG_UF_PADRAO,
    validar_pastas_drive,
)
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
    CertificadoRejeitadoError,
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
    obter_rejeicao_certificado,
    preencher_uf,
    realizar_login_sieg,
    voltar_para_tabela_empresas,
)
from utilitarios import extrair_cnpj, normalizar_texto
from sieg_comum.modais import modal_visivel, botao_modal, campo_upload_modal


def garantir_input_ativo(
    page, descricao, *, rotulo=None, seletor_sem_rotulo=None,
    verificar_rejeicao=False, timeout_ms=15000,
):
    """Marca somente a opcao identificada dentro do ultimo dialogo visivel."""
    limite = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < limite:
        if verificar_rejeicao:
            rejeicao = obter_rejeicao_certificado(page)
            if rejeicao:
                raise CertificadoRejeitadoError(rejeicao)

        modal = modal_visivel(page, timeout=min(timeout_ms, 1000))
        if rotulo is not None:
            campos = modal.get_by_role("checkbox", name=rotulo).or_(
                modal.get_by_role("radio", name=rotulo)
            ).or_(modal.get_by_label(rotulo).and_(modal.locator("input[type='checkbox'], input[type='radio']")))
        elif seletor_sem_rotulo:
            # Compatibilidade temporária: o código legado não registrava os
            # rótulos destas opções. O caminho fica restrito ao diálogo ativo.
            campos = modal.locator(seletor_sem_rotulo)
        else:
            raise ValueError("Informe o rotulo da opcao a marcar.")
        visiveis = [campo for campo in campos.all() if campo.is_visible()]
        if len(visiveis) == 1:
            campo = visiveis[0]
            if campo.is_checked():
                print(f"  ✓ Opção já estava ativa: {descricao}")
                return
            if campo.is_enabled():
                campo.check(force=True, timeout=5000)
                print(f"  ✅ Opção ativada: {descricao}")
                return
        page.wait_for_timeout(200)

    raise TimeoutError(
        f"Não foi possível identificar uma única opção disponível: {descricao}. "
        "A tela após o upload não chegou ao estado esperado."
    )


def clicar_salvar_e_continuar(page, etapa):
    """Clica no botão exato da etapa atual e aguarda a interface avançar."""
    botao = botao_modal(page, "Salvar e continuar")
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

    if not preencher_uf(page, SIEG_UF_PADRAO):
        raise RuntimeError(f"Não foi possível selecionar a UF {SIEG_UF_PADRAO}")

    clicar_salvar_e_continuar(page, "cadastro")

    garantir_input_ativo(
        page, "atualizacao do certificado",
        seletor_sem_rotulo="xpath=.//section[2]/section/div/label/input",
    )

    if not clicar_botao_atualizar_certificado(page):
        raise RuntimeError(
            "Botão de atualização do certificado não encontrado"
        )


def enviar_certificado_candidato(page, candidato, cnpj, nome_empresa):
    """Envia um candidato; apenas uma rejeição explícita permite tentar outro."""
    preparar_tela_upload_certificado(page, cnpj, nome_empresa)
    campo_file = campo_upload_modal(page, "file")
    campo_file.wait_for(state="attached", timeout=15000)
    campo_file.set_input_files({
        "name": candidato["arquivo_nome"],
        "mimeType": "application/x-pkcs12",
        "buffer": candidato["pfx_bytes"],
    })

    campo_pass = campo_upload_modal(page, "password")
    campo_pass.wait_for(state="visible", timeout=15000)
    campo_pass.fill(candidato["senha"])
    campo_pass.dispatch_event("input")
    senha_aceita, mensagem = aguardar_validacao_senha_certificado(page)
    if senha_aceita is False:
        raise CertificadoRejeitadoError(mensagem)
    if senha_aceita is not True:
        raise RuntimeError(
            "Upload enviado, mas a validação do SIEG ficou inconclusiva: "
            f"{mensagem}. Nenhum outro candidato será enviado nesta tentativa."
        )

    print(f"  ✅ Senha confirmada pelo SIEG: {mensagem}")
    try:
        clicar_salvar_e_continuar(page, "certificado")
        garantir_input_ativo(
            page, "Docs Fiscais/HUB",
            rotulo=re.compile(r"^\s*Docs\s+Fiscais\s*\/\s*HUB\s*$", re.IGNORECASE),
            verificar_rejeicao=True,
        )
        garantir_input_ativo(
            page, "Controle de Pendências/Iris",
            rotulo=re.compile(r"^\s*Controle\s+de\s+Pend[eê]ncias\s*\/\s*Iris\s*$", re.IGNORECASE),
            verificar_rejeicao=True,
        )
    except CertificadoRejeitadoError:
        raise
    except Exception as erro:
        raise RuntimeError(
            "Falha de navegação após enviar o certificado e validar a senha: "
            f"{erro}. A atualização pode já ter sido salva no SIEG; "
            "nenhum outro candidato será enviado nesta tentativa."
        ) from erro


def executar_automacao_sieg():
    """Orquestra todo o fluxo de automação."""
    email_sieg = os.getenv("SIEG_EMAIL")
    senha_sieg = os.getenv("SIEG_SENHA")
    if not email_sieg or not senha_sieg:
        raise RuntimeError(f"Preencha SIEG_EMAIL e SIEG_SENHA no arquivo {ARQUIVO_ENV}")
    if not SIEG_UF_PADRAO:
        raise RuntimeError(f"Defina SIEG_UF_PADRAO no arquivo {ARQUIVO_ENV}")
    validar_pastas_drive()

    # Autentica no Google Drive
    service = autenticar_drive()
    print("✅ Autenticado no Google Drive com sucesso!")
    print("📁 Criando índice das pastas do Google Drive...")
    indice_drive = criar_indice_pastas_drive(service, DRIVE_ROOT_FOLDER_ID)
    print(f"✅ {indice_drive['total']} pasta(s) indexada(s) em uma única consulta.")

    with sync_playwright() as p:
        print(f"⏱️ Atraso adicional do Playwright: {SIEG_SLOW_MO_MS} ms por ação")
        browser = p.chromium.launch(headless=True, slow_mo=SIEG_SLOW_MO_MS)
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
        empresas_ignoradas = []
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
                empresas_ignoradas.append({"cnpj": cnpj, "nome": nome_empresa})
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
                    try:
                        enviar_certificado_candidato(
                            page, candidato, cnpj, nome_empresa
                        )
                    except CertificadoRejeitadoError as rejeicao:
                        motivo_rejeicao = f"{candidato['pasta_nome']}: {rejeicao}"
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
                    else:
                        certificado_aceito = candidato
                        print("  ✅ Certificado aceito e próxima etapa aberta.")
                        break

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
                    page, "NFS-e Portal Nacional",
                    rotulo=re.compile(r"^\s*NFS-e\s+Portal\s+Nacional\s*$", re.IGNORECASE),
                )

                # "Concluir" pertence à etapa seguinte e só pode ser clicado
                # depois que todas as etapas anteriores forem salvas.
                botao_concluir = botao_modal(page, "Concluir", timeout=30000)
                botao_concluir.wait_for(state="visible", timeout=30000)
                print("  Etapas salvas. Clicando em 'Concluir'...")
                botao_concluir.scroll_into_view_if_needed()
                botao_concluir.click()
                aguardar_interface_pronta(page)
                botao_modal(page, "Confirmar e finalizar").click()
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
            empresas_ignoradas=empresas_ignoradas,
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
