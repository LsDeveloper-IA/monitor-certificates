# Backend do Monitor de Certificados

API Flask responsável pelo cadastro de certificados, relatórios, notificações,
agendamentos e execução controlada das automações.

## Preparar o ambiente

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha o `.env`. As chaves mínimas para a aplicação integrada são:

- `SECRET_KEY`: chave da aplicação Flask.
- `FRONTEND_ORIGIN`: origem autorizada pelo CORS.
- `INTEGRACAO_API_KEY`: autenticação da sincronização de certificados.
- `AUTOMACAO_EXECUTION_KEY`: autenticação das rotas de automação e WhatsContábil.
- `API_MONITOR_URL`: URL usada pelo motor interno ao sincronizar resultados.

O mesmo arquivo documenta as variáveis opcionais de Excel, Google Drive, ODBC,
WhatsContábil e notificações. Nunca adicione `.env`, tokens, credenciais,
certificados, PDFs ou bancos SQLite ao Git.

## Execução

```powershell
python -m flask --app src.main run --host 127.0.0.1 --port 5000 --no-reload
```

A aplicação cria o SQLite local em `src/database/app.db` quando necessário.
Arquivos `.db` e `.sqlite3` são ignorados pelo Git.

## Principais APIs

- `POST /api/certificados/sincronizar`: recebe a lista processada pelo motor e
  exige `X-API-Key` com `INTEGRACAO_API_KEY`.
- `/api/certificados`: consulta e manutenção dos certificados.
- `/api/automacao/*`: execução, interrupção, saúde, histórico e agendamento do
  motor de monitoramento.
- `/api/automacao/sieg-*`: execução sequencial de `automacao-sieg` e `Auto_NC`.
- `GET /api/relatorios/certificados-vencidos`: consolida os relatórios SIEG.
- `/api/whatscontabil/*`: validação da integração de mensagens.

Na sincronização, CPF/CNPJ é normalizado e usado para atualizar o cadastro sem
criar uma duplicata equivalente. O endpoint não envia mensagens por si só.

## Execução sequencial do SIEG

`ExecutorAutomacao` inicia `automacao-sieg` e aguarda seu encerramento. Somente
após código de saída zero inicia `Auto_NC`. Uma falha ou solicitação de parada
marca a etapa seguinte como não executada, evitando sessões concorrentes.

## Testes

Na pasta `certificados-monitor`:

```powershell
python -m pytest
```

Os testes usam banco em memória, arquivos temporários e mocks. Eles não devem
enviar e-mails, mensagens da WhatsContábil nem executar automações reais.

O teste manual que envia um resumo fictício está separado em
`scripts/testar_resumo_atualizacoes_email.py` e só deve ser executado quando um
envio for autorizado.

Logs e históricos de execução são gravados em `runtime/`.
