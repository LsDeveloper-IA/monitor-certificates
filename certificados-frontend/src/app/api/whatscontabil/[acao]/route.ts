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
  if (!['status', 'validar'].includes(acao)) {
    return NextResponse.json({ erro: 'Acao invalida' }, { status: 404 });
  }

  const chaveAdmin = process.env.AUTOMACAO_ADMIN_KEY || '';
  const chaveRecebida = request.headers.get('X-Admin-Key') || '';
  if (!chaveAdmin || !chavesIguais(chaveRecebida, chaveAdmin)) {
    return NextResponse.json({ erro: 'Acesso administrativo negado' }, { status: 401 });
  }

  const chaveBackend = process.env.AUTOMACAO_EXECUTION_KEY;
  if (!chaveBackend) {
    return NextResponse.json({ erro: 'Integracao nao configurada' }, { status: 503 });
  }

  const resposta = await fetch(`${backendUrl}/api/whatscontabil/${acao}`, {
    method: request.method,
    headers: {
      'Content-Type': 'application/json',
      'X-Automation-Key': chaveBackend,
    },
    cache: 'no-store',
  });
  return new NextResponse(await resposta.text(), {
    status: resposta.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export const GET = encaminhar;
export const POST = encaminhar;
