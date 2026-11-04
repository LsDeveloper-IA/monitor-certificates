# Automação de Certificados — Conthabil

Renova os certificados digitais vencidos no portal **Conthabil**. A execução é
feita sem interface gráfica e sem executável: o andamento é enviado para a
saída padrão e acompanhado pelo painel web, junto das automações do SIEG.

## Fluxo

1. Autentica na API do portal com `CONTHABIL_EMAIL` e `CONTHABIL_SENHA`.
2. Lista os certificados com status **vencido**.
3. Localiza a pasta da empresa no Google Drive (`e-CNPJ`), baixa o `.pfx` mais
   recente e lê a senha (`Senha.txt` ou `Senha.gdoc`).
4. Valida localmente: senha, CNPJ do certificado e data de validade futura.
5. Importa os válidos em lotes pelo endpoint `bulk-create`.
6. Confere o resultado na API e grava o relatório em
   `dados\<data-hora>\resultado.csv` e `.md`.

## Configuração

Copie `.env.example` para `.env` e preencha:

```env
CONTHABIL_EMAIL=seu.email@office-ce.com.br
CONTHABIL_SENHA=sua-senha
GOOGLE_DRIVE_PASTA_E_CNPJ_ID=id-da-pasta-e-cnpj
```

Variáveis opcionais:

```env
CONTHABIL_API_URL=https://api.conthabilbr.com/api
GOOGLE_DRIVE_CREDENCIAIS_DIR=
CONTHABIL_LOTE=10
CONTHABIL_SAIDA=
CONTHABIL_SIMULAR=nao
```

O login e a senha ficam somente no `.env` local. Quando iniciada pelo painel,
as variáveis do `.env` da pasta também são carregadas pelo executor.

## Credenciais do Google Drive

A automação reaproveita `credentials.json` e `token.json` do projeto
`monitor-certificates`.

A ordem de busca é:

1. `GOOGLE_DRIVE_CREDENCIAIS_DIR`, quando informado;
2. `automacao-conthabil/credenciais/`;
3. raiz do repositório.

Se o token expirar e não puder ser renovado, gere um novo executando uma das
outras automações do projeto e copie o `token.json`.

## Execução isolada

```powershell
cd automacao-conthabil
python -m pip install -r requirements.txt
python main.py
```

O código de saída segue o padrão das demais automações:

- `0`: execução concluída (com importações ou sem certificados vencidos);
- `1`: havia certificados vencidos, mas nenhum foi importado;
- `2`: falha de login, configuração ou acesso ao Drive;
- `3`: erro inesperado.

## Situações reportadas

| Situação | Significado |
|---|---|
| `IMPORTADO` | Certificado atualizado no portal |
| `VENCIDO_DRIVE` | O `.pfx` do Drive já venceu — precisa do arquivo novo |
| `SEM_ARQUIVO` | Não existe `.pfx` na pasta da empresa |
| `SENHA_NAO_ENCONTRADA` | Nenhuma senha do Drive abriu o `.pfx` |
| `CNPJ_DIVERGENTE` | O certificado pertence a outro CNPJ |
| `ERRO_PORTAL` | O portal recusou (ex.: "O certificado está expirado") |
| `ERRO_DRIVE` | Falha de acesso ao Google Drive |

## Segurança

- As senhas dos certificados não são gravadas em disco nem nos relatórios;
  são usadas apenas em memória e no envio ao portal.
- O `.pfx` baixado fica em `dados\<execução>\` — apague quando não precisar.
- Não versione `.env`, `credenciais/` nem `dados/`.
