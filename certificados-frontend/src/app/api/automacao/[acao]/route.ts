import { timingSafeEqual } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:5000';

function chavesIguais(recebida: string, esperada: string) {
  const a = Buffer.from(recebida);
  const b = Buffer.from(esperada);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function encaminhar(
  request: NextRequest,
  contexto: { params: Promise<{ acao: string }> },
) {
  const { acao } = await contexto.params;
  if (![
    'status',
    'historico',
    'historico-mensagens',
    'executar',
    'parar',
    'sieg-status',
    'sieg-executar',
    'sieg-parar',
    'agendador-status',
    'agendador-configurar',
    'saude',
  ].includes(acao)) {
    return NextResponse.json({ erro: 'Acao invalida' }, { status: 404 });
  }

  const chaveAdmin = process.env.AUTOMACAO_ADMIN_KEY || '';
  const chaveRecebida = request.headers.get('X-Admin-Key') || '';
  const origem = request.headers.get('origin') || '';
  const host = request.headers.get('host') || '';
  const ambienteLocal = process.env.NODE_ENV !== 'production' || host.includes('localhost') || origem.includes('localhost');

  const acessoPermitido =
    !chaveRecebida && ambienteLocal
      ? true
      : !!chaveAdmin && chavesIguais(chaveRecebida, chaveAdmin);

  if (!acessoPermitido) {
    return NextResponse.json({ erro: 'Acesso administrativo negado' }, { status: 401 });
  }

  const chaveBackend = process.env.AUTOMACAO_EXECUTION_KEY;
  if (!chaveBackend) {
    return NextResponse.json(
      { erro: 'Execucao da automacao nao configurada' },
      { status: 503 },
    );
  }

  const resposta = await fetch(`${backendUrl}/api/automacao/${acao}`, {
    method: request.method,
    headers: {
      'Content-Type': 'application/json',
      'X-Automation-Key': chaveBackend,
    },
    body: request.method === 'POST' ? await request.text() : undefined,
    cache: 'no-store',
  });
  const texto = await resposta.text();
  return new NextResponse(texto, {
    status: resposta.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export const GET = encaminhar;
export const POST = encaminhar;
