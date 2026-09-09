Monitor de Certificados

Sistema integrado para monitoramento de certificados digitais, automação de rotinas no SIEG, sincronização de dados e visualização dos resultados em um painel web.

O projeto reúne frontend, backend, automações Playwright e um pacote compartilhado para operações comuns no SIEG e no Google Drive.

Visão geral

O repositório é dividido em quatro frentes principais:

Módulo

Responsabilidade

certificados-frontend/

Painel web em Next.js para certificados, relatórios, filtros, histórico, logs e controle das automações.

certificados-monitor/

API Flask, banco SQLite, sincronização, agendamentos, notificações e executor dos motores de automação.

automacao-sieg/

Atualiza certificados vencidos no SIEG utilizando certificados localizados no Google Drive.

Auto_NC/

Localiza empresas ativas sem certificado A1, procura arquivos correspondentes no Drive e tenta realizar o cadastro no SIEG.

sieg_comum/

Código compartilhado entre as automações: login, navegação, modais, UF, Google Drive, identidade e validação de certificados.

scripts/

Scripts auxiliares para inicialização do ambiente local.

Arquitetura

                     ┌─────────────────────────┐
                     │ certificados-frontend   │
                     │ Next.js + React         │
                     └────────────┬────────────┘
                                  │
                                  │ HTTP / API
                                  ▼
                     ┌─────────────────────────┐
                     │ certificados-monitor    │
                     │ Flask + SQLite          │
                     └───────┬─────────┬───────┘
                             │         │
                   execução  │         │ sincronização
                             │         │
               ┌─────────────▼───┐     │
               │ automacao-sieg  │     │
               │ Playwright      │     │
               └─────────────┬───┘     │
                             │         │
                             ▼         │
                    ┌────────────────┐  │
                    │    Auto_NC     │  │
                    │   Playwright   │  │
                    └────────┬───────┘  │
                             │          │
                  ┌──────────▼──────────▼───┐
                  │      sieg_comum/       │
                  │ SIEG + Google Drive    │
                  └────────────────────────┘

As duas automações do SIEG são executadas em sequência, evitando duas sessões concorrentes utilizando a mesma conta.

Fluxo das automações SIEG

Quando a execução SIEG é iniciada pelo painel, o backend controla os motores na seguinte ordem:

1. automacao-sieg
        ↓
2. Auto_NC

A segunda etapa só começa quando a primeira termina com sucesso.

Caso uma etapa falhe ou seja interrompida, a próxima não é iniciada.

1. Certificados vencidos — automacao-sieg

Fluxo principal:

Google Drive
    ↓
Indexação das pastas
    ↓
Login no SIEG
    ↓
Gerenciar CNPJs/CPFs
    ↓
Filtro: Certificado Vencido
    ↓
Paginação de até 200 registros
    ↓
Localização da empresa
    ↓
Confirmação do CNPJ da linha
    ↓
Edição do cadastro
    ↓
Preenchimento da UF, quando necessário
    ↓
Busca dos certificados candidatos no Drive
    ↓
Validação local do PFX e da senha
    ↓
Upload no SIEG
    ↓
Validação da resposta do SIEG
    ↓
Conclusão do cadastro
    ↓
Checkpoint + relatório

A busca no Google Drive utiliza um índice em memória para evitar consultar a pasta raiz repetidamente durante a mesma execução.

Os candidatos são avaliados por compatibilidade do nome da empresa, priorizando correspondências exatas.

Quando o SIEG rejeita explicitamente um certificado ou sua senha, a automação pode tentar o próximo candidato disponível.

Se a resposta do SIEG após o upload for inconclusiva, outro certificado não é enviado automaticamente para evitar uma possível escrita duplicada.

2. Empresas sem certificado — Auto_NC

A Auto_NC percorre os cadastros do SIEG e identifica empresas que:

estão marcadas como Ativo na Sieg;

não possuem certificado A1 cadastrado;

possuem uma pasta correspondente disponível no Google Drive.

Fluxo simplificado:

SIEG
 ↓
Leitura das empresas
 ↓
Verificação do status do certificado
 ↓
Empresa sem certificado
 ↓
Busca da pasta no Google Drive
 ↓
Localização do PFX + senha
 ↓
Abertura do cadastro
 ↓
Cadastro do certificado A1
 ↓
Atualização do relatório

A automação também gera arquivos utilizados pelo painel para representar a base consultada e as empresas que continuam sem certificado.

Código compartilhado — sieg_comum

As operações reutilizadas pelas duas automações ficam centralizadas em sieg_comum/.

sieg_comum/
├── __init__.py
├── certificados.py
├── configuracao.py
├── drive.py
├── identidade.py
├── modais.py
├── navegacao.py
├── sessao.py
└── tests/

Responsabilidades

Arquivo

Responsabilidade

sessao.py

Login e reconhecimento de sessão autenticada no SIEG.

navegacao.py

Esperas, navegação, edição de empresa e preenchimento de UF.

modais.py

Localização de diálogos, botões e campos de upload.

drive.py

OAuth, listagem, downloads, Google Docs, busca de pastas e leitura de senhas.

identidade.py

Normalização de nomes e documentos.

certificados.py

Leitura e validação local dos certificados digitais.

configuracao.py

Leitura e validação de parâmetros de ambiente.

A autenticação do Google Drive utiliza token.json.

Tecnologias

Backend

Python

Flask

SQLite

SQLAlchemy

Google Drive API

Playwright

Frontend

Next.js 15

React 19

TypeScript

Axios

Tailwind CSS

Automação

Python

Playwright

Chromium

cryptography

Google Drive API

Google OAuth

python-docx

Estrutura do repositório

monitor-certificates/
│
├── Auto_NC/
│   ├── main.py
│   ├── README.md
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│
├── automacao-sieg/
│   ├── main.py
│   ├── automacao.py
│   ├── config.py
│   ├── drive_service.py
│   ├── persistencia.py
│   ├── sieg_service.py
│   ├── utilitarios.py
│   ├── README.md
│   ├── requirements.txt
│   └── tests/
│
├── certificados-monitor/
│   ├── automation_engine/
│   ├── src/
│   ├── tests/
│   ├── runtime/
│   ├── README.md
│   └── requirements.txt
│
├── certificados-frontend/
│   ├── public/
│   ├── src/
│   ├── README.md
│   ├── package.json
│   └── tsconfig.json
│
├── sieg_comum/
│   ├── certificados.py
│   ├── configuracao.py
│   ├── drive.py
│   ├── identidade.py
│   ├── modais.py
│   ├── navegacao.py
│   ├── sessao.py
│   └── tests/
│
├── scripts/
├── README.md
└── package.json

Requisitos

Para executar o projeto localmente:

Python

Node.js

npm

Google Chrome/Chromium via Playwright

credenciais OAuth do Google Drive

acesso válido ao SIEG

Ambiente principal utilizado pelo projeto: Windows + PowerShell.

Instalação

Clone o repositório:

git clone https://github.com/LsDeveloper-IA/monitor-certificates.git
cd monitor-certificates

Backend

cd certificados-monitor
python -m pip install -r requirements.txt

Automação de certificados vencidos

cd ..\automacao-sieg
python -m pip install -r requirements.txt
python -m playwright install chromium

Auto_NC

cd ..\Auto_NC
python -m pip install -r requirements.txt

Frontend

cd ..\certificados-frontend
npm install

Configuração

Cada módulo possui seu próprio arquivo .env.example.

Crie os arquivos de ambiente antes da primeira execução.

Backend

cd certificados-monitor
Copy-Item .env.example .env

Variáveis principais:

SECRET_KEY=
FRONTEND_ORIGIN=http://localhost:3000

INTEGRACAO_API_KEY=
AUTOMACAO_EXECUTION_KEY=

API_MONITOR_URL=http://127.0.0.1:5000

O backend também possui configurações opcionais para integrações, notificações, Excel, Google Drive e ODBC.

Frontend

Crie:

certificados-frontend/.env.local

Exemplo:

BACKEND_URL=http://localhost:5000
AUTOMACAO_EXECUTION_KEY=
AUTOMACAO_ADMIN_KEY=

AUTOMACAO_EXECUTION_KEY deve utilizar o mesmo valor configurado no backend.

Automação SIEG

Arquivo:

automacao-sieg/.env

Exemplo:

SIEG_EMAIL=
SIEG_SENHA=

SIEG_SLOW_MO_MS=0
SIEG_UF_PADRAO=CE

DRIVE_ROOT_FOLDER_ID=
DRIVE_RELATORIOS_FOLDER_ID=

Também deve existir:

automacao-sieg/credentials.json

Na primeira autenticação do Google, será gerado:

automacao-sieg/token.json

Auto_NC

Arquivo:

Auto_NC/.env

Exemplo:

SIEG_EMAIL=
SIEG_SENHA=

SIEG_SLOW_MO_MS=0

GOOGLE_DRIVE_FOLDER_ID=
AUTO_NC_REPORT_FOLDER_ID=

Variáveis opcionais:

GOOGLE_DRIVE_CREDENTIALS=credentials.json
GOOGLE_DRIVE_TOKEN=token.json
AUTO_NC_RELATORIO_PATH=

Execução integrada

O modo mais simples de iniciar o sistema localmente é pelo frontend:

cd certificados-frontend
npm run dev

O comando chama o script de desenvolvimento do projeto e inicia:

Backend Flask
http://127.0.0.1:5000

Frontend Next.js
http://localhost:3000

Para iniciar apenas o frontend, utilizando um backend que já esteja rodando:

npm run dev:frontend

Execução isolada

Backend

cd certificados-monitor

python -m flask --app src.main run `
    --host 127.0.0.1 `
    --port 5000 `
    --no-reload

Certificados vencidos

cd automacao-sieg
python main.py

Auto_NC

cd Auto_NC
python main.py

API

O backend disponibiliza endpoints para certificados, relatórios e controle das automações.

Principais rotas:

POST /api/certificados/sincronizar

/api/certificados

/api/automacao/*

/api/automacao/sieg-*

GET /api/relatorios/certificados-vencidos

/api/whatscontabil/*

A sincronização da automação utiliza autenticação por chave.

Exemplo de cabeçalho:

X-API-Key: <INTEGRACAO_API_KEY>

Persistência e relatórios

Certificados vencidos

A automação mantém um checkpoint local:

automacao-sieg/
└── registros/
    └── checkpoint.json

O checkpoint registra os CNPJs concluídos com sucesso durante o dia.

Caso a execução seja reiniciada no mesmo dia, empresas já concluídas podem ser ignoradas.

O resumo da execução é enviado ao Google Drive no formato:

resumo_AAAAMMDD_HHMMSS.json

A automação mantém os 10 relatórios mais recentes na pasta configurada.

Auto_NC

A automação utiliza arquivos JSON para disponibilizar os resultados da leitura do SIEG.

Entre eles:

empresas_sieg.json
empresas_sem_certificado.json

O relatório de empresas sem certificado também pode ser publicado no Google Drive.

Logs

O backend mantém informações de execução em:

certificados-monitor/runtime/

O executor registra:

início da execução;

duração;

progresso;

código de saída;

erros;

logs dos motores;

histórico das execuções.

Testes

Backend

cd certificados-monitor
python -X utf8 -m unittest discover -s tests

Automação SIEG

cd automacao-sieg
python -X utf8 -m unittest discover -s tests

Auto_NC

cd Auto_NC
python -X utf8 -m unittest discover -s tests

Código compartilhado

Na raiz do repositório:

python -X utf8 -m unittest discover -s sieg_comum/tests

Frontend

cd certificados-frontend
npm run build

Segurança

Arquivos com credenciais ou dados locais não devem ser enviados ao Git.

Mantenha fora do repositório:

.env
.env.local

credentials.json
token.json

*.db
*.sqlite
*.sqlite3

__pycache__/
*.pyc

registros/
runtime/

As credenciais do Google Drive são persistidas utilizando OAuth em token.json.

Nunca versione:

usuário e senha do SIEG;

tokens do Google;

chaves de API;

bancos com dados de clientes;

certificados .pfx ou .p12;

senhas de certificados.

Desenvolvimento

Ao alterar código utilizado pelas duas automações, prefira implementar a mudança em:

sieg_comum/

Isso evita duplicação entre:

automacao-sieg/
Auto_NC/

O pacote compartilhado não inicia navegador nem executa automações automaticamente quando importado.

Fluxo resumido do sistema

                 Google Drive
                      │
                      ▼
        ┌──────────────────────────┐
        │ automacao-sieg           │
        │ certificados vencidos    │
        └────────────┬─────────────┘
                     │
                     ▼
                  SIEG
                     │
                     ▼
        ┌──────────────────────────┐
        │ Auto_NC                  │
        │ sem certificado A1       │
        └────────────┬─────────────┘
                     │
                     ▼
               Relatórios JSON
                     │
                     ▼
        ┌──────────────────────────┐
        │ certificados-monitor     │
        │ Flask / SQLite           │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ certificados-frontend    │
        │ Next.js / React          │
        └──────────────────────────┘

Documentação dos módulos

Cada componente possui documentação própria:

automacao-sieg/README.md
Auto_NC/README.md
sieg_comum/README.md
certificados-monitor/README.md
certificados-frontend/README.md

Consulte esses arquivos para detalhes específicos de cada módulo.
