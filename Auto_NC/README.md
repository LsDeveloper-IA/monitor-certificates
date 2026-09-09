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
- Salva `empresas_sieg.json` e `empresas_sem_certificado.json` localmente e
  envia o relatório para a pasta configurada.
- O navegador roda em modo invisível (`headless`).

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

- `GOOGLE_DRIVE_CREDENTIALS`: caminho de `credentials.json`.
- `GOOGLE_DRIVE_TOKEN`: caminho de `token.json`.
- `AUTO_NC_RELATORIO_PATH`: caminho do relatório JSON local.

Os dois IDs de pasta são obrigatórios. A primeira autorização do Google pode
abrir o fluxo OAuth; depois, a credencial é persistida em `token.json`.

## Instalação e execução isolada

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

O caminho válido é `Auto_NC/main.py`. A antiga pasta aninhada
`Auto_NC/Auto_NC/` não faz parte da execução.

## Testes

```powershell
python -X utf8 -m unittest discover -s tests
```

O pacote `sieg_comum` deve permanecer na raiz do repositório.
