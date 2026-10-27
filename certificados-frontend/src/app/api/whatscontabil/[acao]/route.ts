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

  const chaveAdmin = (process.env.AUTOMACAO_ADMIN_KEY || '').trim();
  const chaveRecebida = (request.headers.get('X-Admin-Key') || '').trim();
  const origem = request.headers.get('origin') || '';
  const host = request.headers.get('host') || '';

  function hostLocal(valor: string) {
    const hostSemPorta = (valor || '')
      .replace(/^https?:\/\//, '')
      .split('/')[0]
      .split(':')[0]
      .replace(/^\[/, '')
      .replace(/\]$/, '');
    if (!hostSemPorta) return false;
    if (
      hostSemPorta === 'localhost' ||
      hostSemPorta === '127.0.0.1' ||
      hostSemPorta === '::1'
    ) {
      return true;
    }
    const partes = hostSemPorta.split('.');
    if (
      partes.length === 4 &&
      partes.every((parte) => /^\d+$/.test(parte))
    ) {
      const [primeiro, segundo] = partes.map(Number);
      if (primeiro === 10) return true;
      if (primeiro === 192 && segundo === 168) return true;
      if (primeiro === 172 && segundo >= 16 && segundo <= 31) return true;
    }
    return false;
  }

  const ambienteLocal = process.env.NODE_ENV !== 'production' || hostLocal(host) || hostLocal(origem);

  const acessoPermitido =
    !chaveRecebida && ambienteLocal
      ? true
      : !!chaveAdmin && chavesIguais(chaveRecebida, chaveAdmin);

  if (!acessoPermitido) {
    return NextResponse.json(
      {
        erro:
          'Acesso administrativo negado. Informe a chave configurada em AUTOMACAO_ADMIN_KEY ou execute a aplicacao em localhost/127.0.0.1.',
      },
      { status: 401 },
    );
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
