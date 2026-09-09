# Monitor de Certificados

Aplicação para acompanhar certificados digitais, executar rotinas no SIEG e
consolidar os resultados em um painel web. O repositório reúne o frontend, a
API, duas automações Playwright e o código compartilhado entre elas.

## Componentes

| Pasta | Responsabilidade |
| --- | --- |
| `certificados-frontend/` | Painel Next.js para certificados, pendências, relatórios e automações. |
| `certificados-monitor/` | API Flask, banco local, agendamentos, integrações e executor dos motores. |
| `automacao-sieg/` | Atualiza no SIEG os certificados vencidos encontrados no Google Drive. |
| `Auto_NC/` | Identifica empresas ativas sem certificado e gera o relatório correspondente. |
| `sieg_comum/` | Login, navegação e cliente do Drive usados pelas duas automações. |
| `scripts/` | Inicialização do ambiente local. |

## Fluxo das automações SIEG

Ao iniciar a automação SIEG pelo painel, o backend executa os motores em uma
única fila:

1. `automacao-sieg`: procura e atualiza certificados vencidos.
2. `Auto_NC`: lê a lista após as atualizações e identifica quem continua sem
   certificado.

A segunda etapa só começa quando a primeira termina com sucesso. Se houver
falha ou interrupção, ela não é iniciada. Isso impede duas sessões simultâneas
na mesma conta do SIEG.

## Preparação local no Windows

Requisitos: Python, Node.js, npm e Chromium do Playwright.

```powershell
cd certificados-monitor
python -m pip install -r requirements.txt

cd ..\automacao-sieg
python -m pip install -r requirements.txt
python -m playwright install chromium

cd ..\certificados-frontend
npm install
```

Copie e preencha os exemplos de configuração de cada componente:

- `certificados-monitor/.env.example` → `certificados-monitor/.env`
- `certificados-frontend/.env.example` → `certificados-frontend/.env.local`
- `automacao-sieg/.env.example` → `automacao-sieg/.env`
- `Auto_NC/.env.example` → `Auto_NC/.env`

Mantenha `.env`, `credentials.json`, `token.json`, bancos locais e relatórios
fora do Git.

## Execução integrada

Na pasta do frontend:

```powershell
npm run dev
```

O script inicia o backend em `http://127.0.0.1:5000`, aguarda a API responder e
abre o frontend em `http://localhost:3000`. Os logs do backend ficam em
`certificados-monitor/runtime/`. Ao encerrar o Next.js, o processo Flask aberto
pelo script também é encerrado.

## Testes

```powershell
cd certificados-monitor
python -X utf8 -m unittest discover -s tests

cd ..\automacao-sieg
python -X utf8 -m unittest discover -s tests

cd ..\Auto_NC
python -X utf8 -m unittest discover -s tests

cd ..
python -X utf8 -m unittest discover -s sieg_comum/tests
```

Consulte o README de cada pasta para configuração e execução isolada.
