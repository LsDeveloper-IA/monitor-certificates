# Auto_NC

Automação de leitura do SIEG que identifica empresas ativas sem certificado A1,
consulta as pastas correspondentes no Google Drive e publica um relatório JSON.
Ela é executada depois da atualização de certificados vencidos quando iniciada
pelo painel.

## Regras principais

- Percorre a tabela `Gerenciar CNPJs/CPFs` do SIEG.
- Processa apenas linhas cujo campo **Ativo na Sieg** esteja marcado.
- Considera o status da coluna de certificado, sem misturar outras colunas.
- Registra empresas que continuam sem certificado e tenta localizar seus
  arquivos pela razão social no Drive.
- Salva `empresas_sieg.json` e `empresas_sem_certificado.json` em
  `storage/auto_nc/` e envia o relatório para a pasta configurada.
- O navegador roda em modo invisível (`headless`).
- Com `AUTO_NC_EMPRESA_ALVO` ou `AUTO_NC_CNPJ_ALVO`, processa somente a empresa
  indicada e encerra, sem alterar os relatórios existentes.

## Configuração

Copie `.env.example` para `.env`:

```env
SIEG_EMAIL=seu-email
SIEG_SENHA=sua-senha
SIEG_SLOW_MO_MS=0
GOOGLE_DRIVE_FOLDER_ID=id-da-pasta-das-empresas
AUTO_NC_REPORT_FOLDER_ID=id-da-pasta-de-relatorios
```

Opções adicionais:

- `GOOGLE_DRIVE_CREDENTIALS`: caminho de `credentials.json`. Padrão:
  `storage/secrets/auto_nc/credentials.json`.
- `GOOGLE_DRIVE_TOKEN`: caminho de `token.json`. Padrão:
  `storage/secrets/auto_nc/token.json`.
- `AUTO_NC_RELATORIO_PATH`: caminho do relatório JSON local. Padrão:
  `storage/auto_nc/empresas_sem_certificado.json`.
- `STORAGE_DIR`: raiz alternativa para os dados gerados.

Os dois IDs de pasta são obrigatórios. A primeira autorização do Google pode
abrir o fluxo OAuth; depois, a credencial é persistida em
`storage/secrets/auto_nc/token.json`.

Se `GOOGLE_DRIVE_FOLDER_ID` não for informado no `automacoes/auto_nc/.env`, o
valor é herdado do `.env` da raiz do projeto. A pasta precisa ser a que contém
uma subpasta por empresa (com o `.pfx` e o arquivo de senha), não a pasta de
relatórios.

## Instalação e execução isolada

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

O caminho válido é `automacoes/auto_nc/main.py`.

## Testes

```powershell
cd automacoes/auto_nc
python -X utf8 -m unittest discover -s tests
```

O pacote compartilhado fica em `automacoes/sieg_comum/` e é importado pelas
automações do SIEG e do Auto_NC.
