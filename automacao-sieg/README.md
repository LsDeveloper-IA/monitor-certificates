# Automação de Certificados Vencidos no SIEG

Automação Playwright que consulta certificados vencidos no SIEG, localiza
candidatos no Google Drive e atualiza o cadastro da empresa. O navegador roda
em modo invisível (`headless`).

## Fluxo

1. Autentica no Google Drive e cria um índice das pastas das empresas.
2. Entra no SIEG e abre `Gerenciar CNPJs/CPFs`.
3. Filtra empresas com certificado vencido e exibe até 200 linhas.
4. Confirma o CNPJ da linha antes de abrir a edição.
5. Preenche a UF configurada somente quando o cadastro estiver vazio.
6. Testa os certificados candidatos em ordem de similaridade.
7. Conclui as opções `Docs Fiscais/HUB`, `Controle de Pendências/Iris` e
   `NFS-e Portal Nacional` no diálogo ativo.
8. Registra checkpoint, relatório e evidências de falha.

Uma rejeição explícita de senha ou certificado permite testar o próximo
candidato. Se a resposta do SIEG for inconclusiva após o upload, nenhum outro
arquivo é enviado para aquela empresa, pois a atualização pode já ter sido
salva.

## Configuração

Copie `.env.example` para `.env`:

```env
SIEG_EMAIL=seu-email
SIEG_SENHA=sua-senha
SIEG_SLOW_MO_MS=0
SIEG_UF_PADRAO=CE
DRIVE_ROOT_FOLDER_ID=id-da-pasta-das-empresas
DRIVE_RELATORIOS_FOLDER_ID=id-da-pasta-de-relatorios
```

Os IDs das pastas e `SIEG_UF_PADRAO` são obrigatórios. A UF aceita qualquer
sigla brasileira; ela não substitui um Estado já preenchido no SIEG.

Coloque `credentials.json` nesta pasta. Na primeira autorização, o fluxo OAuth
gera `token.json`; as execuções seguintes usam esse arquivo seguro em JSON.

`SIEG_SLOW_MO_MS` adiciona atraso após ações do Playwright. Use `0` para a
execução normal e aumente somente se uma medição real indicar instabilidade.

## Instalação e execução isolada

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

O `main.py` faz até três tentativas completas. O intervalo cresce a cada falha.
Quando iniciada pelo painel, esta automação sempre termina antes de `Auto_NC`
começar.

## Retomada e arquivos gerados

```text
registros/
├── checkpoint.json
├── resumo_AAAAMMDD_HHMMSS.txt
└── erros/
    ├── erro_CNPJ_DATA_HORA.png
    └── erro_CNPJ_DATA_HORA.html
```

O checkpoint recebe o CNPJ somente após o fluxo inteiro terminar. CNPJs já
concluídos no dia são ignorados em uma nova tentativa. O resumo também é
enviado para `DRIVE_RELATORIOS_FOLDER_ID`.

## Seletores e código compartilhado

Modais são localizados pelo último diálogo visível. Botões e opções usam papel,
rótulo ou tooltip, evitando índices absolutos como `div[5]` e `div[6]`. Login,
navegação, UF e Google Drive ficam em `sieg_comum/`.

## Testes

```powershell
python -X utf8 -m unittest discover -s tests
```

Os testes usam páginas locais e mocks; não fazem login nem upload real.
Credenciais, tokens, checkpoints, relatórios e evidências não devem ser
versionados.
