import re
from time import perf_counter


TAMANHO_LOTE_ODBC = 100


def dividir_em_lotes(itens, tamanho=TAMANHO_LOTE_ODBC):
    """Divide uma lista para evitar comandos SQL com parametros demais."""
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def normalizar_cnpj(cnpj):
    """Aceita CNPJ formatado ou sem pontuação e retorna 14 números."""
    somente_numeros = re.sub(r"\D", "", str(cnpj or ""))

    if len(somente_numeros) != 14:
        raise ValueError("O CNPJ precisa conter exatamente 14 números.")

    return somente_numeros


def listar_tabelas(conexao):
    """Retorna as tabelas visíveis para o usuário conectado.

    Esta função consulta somente os metadados do banco. Ela não altera
    registros e não executa INSERT, UPDATE ou DELETE.
    """
    cursor = conexao.cursor()

    try:
        tabelas = []

        for item in cursor.tables(tableType="TABLE"):
            tabelas.append(
                {
                    "catalogo": item.table_cat,
                    "schema": item.table_schem,
                    "nome": item.table_name,
                    "tipo": item.table_type,
                }
            )

        return sorted(
            tabelas,
            key=lambda tabela: (
                str(tabela["schema"] or "").casefold(),
                str(tabela["nome"] or "").casefold(),
            ),
        )
    finally:
        cursor.close()


def filtrar_tabelas_por_nome(tabelas, termos):
    """Filtra localmente a lista de tabelas por palavras do nome."""
    termos_normalizados = [str(termo).casefold() for termo in termos]

    return [
        tabela
        for tabela in tabelas
        if any(
            termo in str(tabela["nome"] or "").casefold()
            for termo in termos_normalizados
        )
    ]


def listar_colunas(conexao, nome_tabela, schema=None):
    """Retorna somente os metadados das colunas de uma tabela."""
    cursor = conexao.cursor()

    try:
        colunas = []

        for item in cursor.columns(
            table=nome_tabela,
            schema=schema,
        ):
            colunas.append(
                {
                    "nome": item.column_name,
                    "tipo": item.type_name,
                    "tamanho": item.column_size,
                    "aceita_nulo": item.nullable,
                    "posicao": item.ordinal_position,
                }
            )

        return sorted(colunas, key=lambda coluna: coluna["posicao"])
    finally:
        cursor.close()


def buscar_cliente_por_cnpj(conexao, cnpj):
    """Busca empresa e contatos pelo CNPJ usando apenas comandos SELECT."""
    cnpj_normalizado = normalizar_cnpj(cnpj)
    cursor = conexao.cursor()

    try:
        cursor.execute(
            """
            SELECT TOP 1
                codi_emp,
                nome_emp,
                cgce_emp,
                email_emp,
                email_leg_emp,
                fone_emp,
                dddf_emp
            FROM bethadba.GEEMPRE
            WHERE REPLACE(
                REPLACE(
                    REPLACE(TRIM(cgce_emp), '.', ''),
                    '/',
                    ''
                ),
                '-',
                ''
            ) = ?
            """,
            cnpj_normalizado,
        )
        empresa = cursor.fetchone()

        if empresa is None:
            return None

        dados_cliente = {
            "codigo": empresa.codi_emp,
            "nome": str(empresa.nome_emp or "").strip(),
            "cnpj": normalizar_cnpj(empresa.cgce_emp),
            "email_empresa": str(empresa.email_emp or "").strip() or None,
            "email_responsavel_legal": (
                str(empresa.email_leg_emp or "").strip() or None
            ),
            "email_atendimento": None,
            "telefone": str(empresa.fone_emp or "").strip() or None,
            "ddd": str(empresa.dddf_emp or "").strip() or None,
            "contatos": [],
            "socios": [],
        }

        cursor.execute(
            """
            SELECT
                I_CONTATO,
                NOME_CONTATO,
                TELEFONE_CONTATO,
                EMAIL_CONTATO
            FROM bethadba.GEEMPRE_CONTATO
            WHERE CODI_EMP = ?
            ORDER BY I_CONTATO
            """,
            dados_cliente["codigo"],
        )

        for contato in cursor.fetchall():
            dados_cliente["contatos"].append(
                {
                    "codigo": contato.I_CONTATO,
                    "nome": str(contato.NOME_CONTATO or "").strip() or None,
                    "telefone": (
                        str(contato.TELEFONE_CONTATO or "").strip() or None
                    ),
                    "email": (
                        str(contato.EMAIL_CONTATO or "").strip() or None
                    ),
                }
            )

        tem_email_contato = any(
            contato.get("email") for contato in dados_cliente["contatos"]
        )

        # Só consulta fontes alternativas quando as prioritárias estão vazias.
        if not tem_email_contato and not dados_cliente["email_empresa"]:
            # A ligação com o atendimento é feita pelo próprio CNPJ.
            cursor.execute(
                """
                SELECT TOP 1 EMAIL
                FROM bethadba.GEEMPRE_ATENDIMENTO
                WHERE REPLACE(
                    REPLACE(
                        REPLACE(TRIM(CNPJ), '.', ''),
                        '/',
                        ''
                    ),
                    '-',
                    ''
                ) = ?
                  AND COALESCE(TRIM(EMAIL), '') <> ''
                """,
                cnpj_normalizado,
            )
            atendimento = cursor.fetchone()
            if atendimento is not None:
                dados_cliente["email_atendimento"] = (
                    str(atendimento.EMAIL or "").strip() or None
                )

        # A planilha exibe os socios de todas as empresas, mesmo quando outro
        # endereco de e-mail ja foi encontrado.
        if dados_cliente["codigo"] is not None:
            # Último recurso: sócios do Onvio ligados pelo código da empresa.
            cursor.execute(
                """
                SELECT DESC_SOCIO, EMAIL
                FROM bethadba.GEQUADROSOCIETARIO_SOCIOS_ONVIO
                WHERE CODI_EMP = ?
                ORDER BY DESC_SOCIO
                """,
                dados_cliente["codigo"],
            )

            for socio in cursor.fetchall():
                dados_cliente["socios"].append(
                    {
                        "nome": (
                            str(socio.DESC_SOCIO or "").strip() or None
                        ),
                        "email": str(socio.EMAIL or "").strip() or None,
                    }
                )

        return dados_cliente
    finally:
        cursor.close()


def escolher_email_cliente(dados_cliente):
    """Escolhe o e-mail conforme a prioridade definida para os alertas."""
    if not dados_cliente:
        return None, None

    for contato in dados_cliente.get("contatos", []):
        if contato.get("email"):
            return contato["email"], "contato"

    if dados_cliente.get("email_empresa"):
        return dados_cliente["email_empresa"], "empresa"

    if dados_cliente.get("email_atendimento"):
        return dados_cliente["email_atendimento"], "atendimento"

    if dados_cliente.get("email_responsavel_legal"):
        return dados_cliente["email_responsavel_legal"], "responsavel_legal"

    for socio in dados_cliente.get("socios", []):
        if socio.get("email"):
            return socio["email"], "socio_onvio"

    return None, None


def buscar_clientes_por_cnpjs(conexao, cnpjs):
    """Carrega empresas, contatos e socios em lotes usando somente SELECT."""
    inicio_consulta = perf_counter()
    cnpjs_normalizados = list(
        dict.fromkeys(normalizar_cnpj(cnpj) for cnpj in cnpjs)
    )
    clientes_por_cnpj = {cnpj: None for cnpj in cnpjs_normalizados}

    if not cnpjs_normalizados:
        return clientes_por_cnpj

    cursor = conexao.cursor()

    try:
        print(
            f"Carregando {len(cnpjs_normalizados)} empresas em lotes "
            f"de até {TAMANHO_LOTE_ODBC}..."
        )

        # 1. Empresas: uma consulta por lote, em vez de uma por CNPJ.
        for lote in dividir_em_lotes(cnpjs_normalizados):
            marcadores = ", ".join("?" for _ in lote)
            cursor.execute(
                f"""
                SELECT
                    codi_emp,
                    nome_emp,
                    cgce_emp,
                    email_emp,
                    email_leg_emp,
                    fone_emp,
                    dddf_emp
                FROM bethadba.GEEMPRE
                WHERE REPLACE(
                    REPLACE(
                        REPLACE(TRIM(cgce_emp), '.', ''),
                        '/',
                        ''
                    ),
                    '-',
                    ''
                ) IN ({marcadores})
                ORDER BY codi_emp
                """,
                *lote,
            )

            for empresa in cursor.fetchall():
                try:
                    cnpj_empresa = normalizar_cnpj(empresa.cgce_emp)
                except ValueError:
                    continue

                # Mantém o primeiro cadastro quando houver CNPJ duplicado.
                if clientes_por_cnpj.get(cnpj_empresa) is not None:
                    continue

                clientes_por_cnpj[cnpj_empresa] = {
                    "codigo": empresa.codi_emp,
                    "nome": str(empresa.nome_emp or "").strip(),
                    "cnpj": cnpj_empresa,
                    "email_empresa": (
                        str(empresa.email_emp or "").strip() or None
                    ),
                    "email_responsavel_legal": (
                        str(empresa.email_leg_emp or "").strip() or None
                    ),
                    "email_atendimento": None,
                    "telefone": str(empresa.fone_emp or "").strip() or None,
                    "ddd": str(empresa.dddf_emp or "").strip() or None,
                    "contatos": [],
                    "socios": [],
                }

        clientes_encontrados = [
            cliente
            for cliente in clientes_por_cnpj.values()
            if cliente is not None
        ]
        clientes_por_codigo = {
            cliente["codigo"]: cliente for cliente in clientes_encontrados
        }
        codigos = list(clientes_por_codigo)
        print(f"Empresas encontradas: {len(clientes_encontrados)}")

        # 2. Todos os contatos das empresas encontradas.
        print("Carregando contatos...")
        for lote in dividir_em_lotes(codigos):
            marcadores = ", ".join("?" for _ in lote)
            cursor.execute(
                f"""
                SELECT
                    CODI_EMP,
                    I_CONTATO,
                    NOME_CONTATO,
                    TELEFONE_CONTATO,
                    EMAIL_CONTATO
                FROM bethadba.GEEMPRE_CONTATO
                WHERE CODI_EMP IN ({marcadores})
                ORDER BY CODI_EMP, I_CONTATO
                """,
                *lote,
            )

            for contato in cursor.fetchall():
                cliente = clientes_por_codigo.get(contato.CODI_EMP)
                if cliente is None:
                    continue
                cliente["contatos"].append(
                    {
                        "codigo": contato.I_CONTATO,
                        "nome": (
                            str(contato.NOME_CONTATO or "").strip() or None
                        ),
                        "telefone": (
                            str(contato.TELEFONE_CONTATO or "").strip()
                            or None
                        ),
                        "email": (
                            str(contato.EMAIL_CONTATO or "").strip() or None
                        ),
                    }
                )

        # 3. Todos os socios, necessarios para a coluna Socio(s) do Excel.
        print("Carregando sócios...")
        for lote in dividir_em_lotes(codigos):
            marcadores = ", ".join("?" for _ in lote)
            cursor.execute(
                f"""
                SELECT CODI_EMP, DESC_SOCIO, EMAIL
                FROM bethadba.GEQUADROSOCIETARIO_SOCIOS_ONVIO
                WHERE CODI_EMP IN ({marcadores})
                ORDER BY CODI_EMP, DESC_SOCIO
                """,
                *lote,
            )

            for socio in cursor.fetchall():
                cliente = clientes_por_codigo.get(socio.CODI_EMP)
                if cliente is None:
                    continue
                cliente["socios"].append(
                    {
                        "nome": str(socio.DESC_SOCIO or "").strip() or None,
                        "email": str(socio.EMAIL or "").strip() or None,
                    }
                )

        # 4. Atendimento só é necessário quando as fontes prioritárias
        # (contato e empresa) não possuem e-mail.
        clientes_sem_email_prioritario = [
            cliente
            for cliente in clientes_encontrados
            if not cliente["email_empresa"]
            and not any(
                contato.get("email") for contato in cliente["contatos"]
            )
        ]
        cnpjs_atendimento = [
            cliente["cnpj"] for cliente in clientes_sem_email_prioritario
        ]

        if cnpjs_atendimento:
            print(
                "Carregando atendimento para "
                f"{len(cnpjs_atendimento)} empresas sem e-mail prioritário..."
            )
            clientes_atendimento = {
                cliente["cnpj"]: cliente
                for cliente in clientes_sem_email_prioritario
            }

            for lote in dividir_em_lotes(cnpjs_atendimento):
                marcadores = ", ".join("?" for _ in lote)
                cursor.execute(
                    f"""
                    SELECT CNPJ, EMAIL
                    FROM bethadba.GEEMPRE_ATENDIMENTO
                    WHERE REPLACE(
                        REPLACE(
                            REPLACE(TRIM(CNPJ), '.', ''),
                            '/',
                            ''
                        ),
                        '-',
                        ''
                    ) IN ({marcadores})
                      AND COALESCE(TRIM(EMAIL), '') <> ''
                    """,
                    *lote,
                )

                for atendimento in cursor.fetchall():
                    try:
                        cnpj_atendimento = normalizar_cnpj(atendimento.CNPJ)
                    except ValueError:
                        continue
                    cliente = clientes_atendimento.get(cnpj_atendimento)
                    if cliente is not None and not cliente["email_atendimento"]:
                        cliente["email_atendimento"] = (
                            str(atendimento.EMAIL or "").strip() or None
                        )

        tempo_total = perf_counter() - inicio_consulta
        print(f"Dados do banco carregados em {tempo_total:.1f} segundos.")
        return clientes_por_cnpj
    finally:
        cursor.close()


def buscar_cnpj_por_nome_exato(conexao, nome):
    """Busca um CNPJ por nomes cadastrais e aceita somente resultado único."""
    nome = str(nome or "").strip()
    nome = re.sub(r"\s*:?[0-9]{14}\s*$", "", nome).strip()
    if not nome:
        return None, "nome_vazio"

    cursor = conexao.cursor()

    try:
        cursor.execute(
            """
            SELECT TOP 2 cgce_emp
            FROM bethadba.GEEMPRE
            WHERE UPPER(TRIM(nome_emp)) = UPPER(?)
               OR UPPER(TRIM(razao_emp)) = UPPER(?)
               OR UPPER(TRIM(fantasia_emp)) = UPPER(?)
               OR UPPER(TRIM(apel_emp)) = UPPER(?)
            ORDER BY codi_emp
            """,
            nome,
            nome,
            nome,
            nome,
        )
        encontrados = cursor.fetchall()

        if not encontrados:
            return None, "nao_encontrado"

        cnpjs = set()
        for item in encontrados:
            try:
                cnpjs.add(normalizar_cnpj(item.cgce_emp))
            except ValueError:
                continue

        if len(cnpjs) != 1:
            return None, "ambiguo"

        return cnpjs.pop(), "unico"
    finally:
        cursor.close()


def preencher_clientes_por_nome(conexao, resultados):
    """Usa empresa ou titular quando o CNPJ não localizou um cadastro."""
    for resultado in resultados:
        if resultado.get("dados_cliente") is not None:
            resultado["criterio_busca_cliente"] = "cnpj"
            continue

        criterios = [
            ("nome_empresa", resultado.get("empresa")),
            ("titular_certificado", resultado.get("titular")),
        ]

        for criterio, nome in criterios:
            cnpj_encontrado, situacao = buscar_cnpj_por_nome_exato(
                conexao,
                nome,
            )

            if situacao == "ambiguo":
                resultado["busca_cliente_ambigua"] = True
                continue

            if not cnpj_encontrado:
                continue

            dados_cliente = buscar_cliente_por_cnpj(
                conexao,
                cnpj_encontrado,
            )
            email, origem_email = escolher_email_cliente(dados_cliente)

            resultado["dados_cliente"] = dados_cliente
            resultado["email"] = email
            resultado["origem_email"] = origem_email
            resultado["criterio_busca_cliente"] = criterio
            resultado["cnpj_localizado_no_banco"] = cnpj_encontrado
            break


def preencher_dados_clientes(resultados, clientes_por_cnpj):
    """Acrescenta os dados do banco aos resultados dos certificados."""
    for resultado in resultados:
        resultado["consulta_email_realizada"] = True
        cnpj = resultado.get("cnpj")
        dados_cliente = clientes_por_cnpj.get(cnpj) if cnpj else None
        email, origem_email = escolher_email_cliente(dados_cliente)

        resultado["dados_cliente"] = dados_cliente
        resultado["email"] = email
        resultado["origem_email"] = origem_email


def identificar_pendencias_email(resultados):
    """Explica por que cada certificado ficou sem e-mail para contato."""
    pendencias = []

    for resultado in resultados:
        if resultado.get("email"):
            continue

        cnpj = resultado.get("cnpj")
        dados_cliente = resultado.get("dados_cliente")

        if not cnpj:
            motivo = "CNPJ não foi encontrado no certificado nem no arquivo."
        elif dados_cliente is None:
            if resultado.get("busca_cliente_ambigua"):
                motivo = (
                    "CNPJ não localizado e a busca pelo nome retornou "
                    "mais de uma empresa. Exige revisão manual."
                )
            else:
                motivo = (
                    "Cadastro não localizado por CNPJ, nome empresarial, "
                    "razão social, fantasia, apelido ou titular."
                )
        else:
            quantidade_contatos = len(dados_cliente.get("contatos", []))
            quantidade_socios = len(dados_cliente.get("socios", []))
            if quantidade_contatos or quantidade_socios:
                motivo = (
                    "E-mail não localizado nos campos consultados de "
                    "contatos, empresa, atendimento, responsável legal "
                    "ou sócios do Onvio. Pode existir em outro cadastro."
                )
            else:
                motivo = (
                    "E-mail não localizado em GEEMPRE, atendimento, "
                    "contatos ou quadro societário do Onvio."
                )

        pendencias.append(
            {
                "empresa": resultado.get("empresa") or "não informada",
                "cnpj": cnpj or "não encontrado",
                "arquivo": resultado.get("arquivo") or "não informado",
                "status": resultado.get("status") or "não informado",
                "criterio_busca": (
                    resultado.get("criterio_busca_cliente")
                    or "nenhum cadastro localizado"
                ),
                "motivo": motivo,
            }
        )

    return pendencias
