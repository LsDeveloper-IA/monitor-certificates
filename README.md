# Monitor de Certificados

Aplicação para acompanhar certificados digitais, executar rotinas no SIEG e
consolidar os resultados em um painel web. O repositório reúne o frontend, a
API, duas automações Playwright, a integração com o Conthabil e o código
compartilhado entre elas.

## Componentes

| Pasta | Responsabilidade |
| --- | --- |
| `certificados-frontend/` | Painel Next.js para certificados, pendências, relatórios e automações. |
| `certificados-monitor/` | API Flask, banco local, agendamentos, integrações e executor dos motores. |
| `automacoes/sieg/` | Atualiza no SIEG os certificados vencidos encontrados no Google Drive. |
| `automacoes/auto_nc/` | Identifica empresas ativas sem certificado e gera o relatório correspondente. |
| `automacoes/conthabil/` | Renova certificados no portal Conthabil usando os arquivos do Google Drive. |
| `automacoes/sieg_comum/` | Login, navegação e cliente do Drive usados pelas automações do SIEG. |
| `config/` | Validação central das variáveis de ambiente do painel. |
| `scripts/` | Inicialização do ambiente local e execução dos testes. |
| `storage/` | Dados gerados: banco, logs, relatórios, planilhas e credenciais. Fora do Git. |

`pyproject.toml` define os pacotes instaláveis e a configuração única do pytest.
O código fica nas pastas acima; `storage/` contém somente dados de execução.

## Fluxo das automações

Ao iniciar a automação pelo painel, o backend executa os motores em uma única
fila:

1. `automacoes/sieg`: procura e atualiza certificados vencidos no SIEG.
2. `automacoes/auto_nc`: lê a lista após as atualizações e identifica quem
   continua sem certificado no SIEG.
3. `automacoes/conthabil`: renova os certificados vencidos no portal Conthabil.

Cada etapa só começa quando a anterior termina com sucesso. Se houver falha ou
interrupção, as próximas não são iniciadas. Isso impede duas sessões
simultâneas na mesma conta do SIEG.

## Preparação local no Windows

Requisitos: Python, Node.js, npm e Chromium do Playwright.

```powershell
# Da raiz do repositorio: pacote do motor e pacote compartilhado do SIEG
python -m pip install -e .
python -m pip install -e automacoes/sieg_comum

cd certificados-monitor
python -m pip install -r requirements.txt

cd ..\automacoes\sieg
python -m pip install -r requirements.txt
python -m playwright install chromium

cd ..\..\certificados-frontend
npm install
```

Copie e preencha os exemplos de configuração de cada componente:

- `certificados-monitor/.env.example` → `certificados-monitor/.env`
- `certificados-frontend/.env.example` → `certificados-frontend/.env.local`
- `automacoes/sieg/.env.example` → `automacoes/sieg/.env`
- `automacoes/auto_nc/.env.example` → `automacoes/auto_nc/.env`
- `automacoes/conthabil/.env.example` → `automacoes/conthabil/.env`

Mantenha `.env`, `credentials.json`, `token.json`, bancos locais e relatórios
fora do Git. Credenciais e tokens OAuth ficam em `storage/secrets/<componente>`:

```text
storage/
├── database/app.db          # banco SQLite do backend
├── runtime/                 # históricos, agendador e logs das execuções
├── automation_engine/       # dados e relatórios do motor de certificados
├── auto_nc/                 # empresas_sieg.json e empresas_sem_certificado.json
├── conthabil/               # downloads e relatórios do Conthabil
├── automacao_sieg/          # checkpoints e evidências
└── secrets/
    ├── backend/             # credentials.json, token.json, token_email.json
    ├── auto_nc/
    └── automacao_sieg/
```

O `storage/` é ignorado pelo Git. Em produção, defina `STORAGE_DIR` para apontar
para outro disco/pasta quando necessário.

## Execução integrada

Na pasta do frontend:

```powershell
npm run dev
```

O script inicia o backend em `http://127.0.0.1:5000`, aguarda a API responder e
abre o frontend em `http://localhost:3000`. Os logs do backend ficam em
`storage/runtime/`. Ao encerrar o Next.js, o processo Flask aberto pelo script
também é encerrado.

## Testes

Execute toda a suite com um único pytest a partir da raiz:

```powershell
.\scripts\test.ps1
```

O script usa o `pyproject.toml` e cobre backend, `automacoes/sieg`,
`automacoes/auto_nc` e `automacoes/sieg_comum`.

Para rodar um recorte específico:

```powershell
python -m pytest certificados-monitor/tests -q
python -m pytest automacoes/sieg/tests -q
python -m pytest automacoes/auto_nc/tests -q
python -m pytest automacoes/sieg_comum/tests -q
```

Consulte o README de cada pasta para configuração e execução isolada.
