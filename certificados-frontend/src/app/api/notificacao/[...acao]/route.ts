import { timingSafeEqual } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';

// No Windows, "localhost" pode resolver para ::1 enquanto o Flask escuta em
// 127.0.0.1. Normalizar para IPv4 evita 500 (ECONNREFUSED) no proxy.
const backendUrl = (process.env.BACKEND_URL || 'http://127.0.0.1:5000')
  .replace('://localhost', '://127.0.0.1')
  .replace(/\/+$/, '');

const acoesPermitidas = new Set([
  'configurar-email',
  'configurar-whatsapp',
  'configurar-destinatarios',
  'teste-email',
  'teste-whatsapp',
  'verificar-agora',
  'agendador/status',
  'agendador/iniciar',
  'agendador/parar',
  'preview',
]);

function chavesIguais(recebida: string, esperada: string) {
  const a = Buffer.from(recebida);
  const b = Buffer.from(esperada);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function encaminhar(
  request: NextRequest,
  contexto: { params: Promise<{ acao: string[] }> },
) {
  const { acao } = await contexto.params;
  const caminho = acao.join('/');
  if (!acoesPermitidas.has(caminho)) {
    return NextResponse.json({ erro: 'Acao invalida' }, { status: 404 });
  }

  const chaveAdmin = process.env.AUTOMACAO_ADMIN_KEY || '';
  const chaveRecebida = request.headers.get('X-Admin-Key') || '';
  if (!chaveAdmin || !chavesIguais(chaveRecebida, chaveAdmin)) {
    return NextResponse.json(
      { erro: 'Acesso administrativo negado' },
      { status: 401 },
    );
  }

  const chaveBackend = (process.env.AUTOMACAO_EXECUTION_KEY || '').trim();
  if (!chaveBackend) {
    return NextResponse.json(
      { erro: 'Integracao de notificacoes nao configurada' },
      { status: 503 },
    );
  }

  const destino = new URL(`${backendUrl}/api/notificacao/${caminho}`);
  destino.search = request.nextUrl.search;
  const resposta = await fetch(destino, {
    method: request.method,
    headers: {
      'Content-Type': 'application/json',
      'X-Automation-Key': chaveBackend,
      'X-Local-Proxy': 'local',
    },
    body: request.method === 'GET' ? undefined : await request.text(),
    cache: 'no-store',
  });

  return new NextResponse(await resposta.text(), {
    status: resposta.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export const GET = encaminhar;
export const POST = encaminhar;
