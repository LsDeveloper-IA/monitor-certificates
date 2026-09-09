# Frontend do Monitor de Certificados

Painel Next.js 15 para consultar certificados, acompanhar pendências, abrir o
relatório de certificados vencidos e controlar as automações do backend.

## Telas

- `/`: visão geral, filtros, busca, cadastro e estatísticas dos certificados.
- O painel e o modal da página inicial exibem execução, agendamento, progresso,
  histórico e logs da automação de monitoramento.
- `/certificados-vencidos`: consolidação dos resultados das automações SIEG.

As rotas em `src/app/api/` funcionam como proxy para o Flask. A chave interna
fica apenas no servidor Next.js e não é enviada ao navegador.

## Configuração

Copie `.env.example` para `.env.local`:

```env
BACKEND_URL=http://localhost:5000
AUTOMACAO_EXECUTION_KEY=mesmo-valor-do-backend
AUTOMACAO_ADMIN_KEY=senha-administrativa-local
```

`AUTOMACAO_EXECUTION_KEY` deve ser igual à variável do backend.
`AUTOMACAO_ADMIN_KEY` protege as ações administrativas expostas pelo proxy.

## Instalação e execução

```powershell
npm install
npm run dev
```

Neste repositório, `npm run dev` chama `scripts/dev.ps1`: inicia o Flask em
segundo plano na porta 5000 e depois o Next.js na porta 3000. Para iniciar
somente o frontend, com um backend já disponível, use:

```powershell
npm run dev:frontend
```

## Verificação

```powershell
npm run build
```

O frontend espera o backend em `BACKEND_URL`; sem ele, consultas e ações de
automação retornam erro pelo proxy.
