import { NextRequest, NextResponse } from 'next/server';

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const caminho = path.join('/');
  const metodos: Record<string, string[]> = { certificados: ['GET', 'POST'], imagens: ['GET'], registros: ['PUT', 'DELETE'] };
  if (!/^(certificados|imagens|registros)\/[1-9]\d*$/.test(caminho) || !metodos[path[0]].includes(request.method)) return new NextResponse(null, { status: 404 });
  // Histórico liberado aos usuários do painel local, conforme autorização.
  const origem = request.headers.get('origin');
  let mesmaOrigem = !origem;
  try { if (origem) mesmaOrigem = new URL(origem).host === request.headers.get('host'); } catch { mesmaOrigem = false; }
  if (request.method !== 'GET' && (request.headers.get('sec-fetch-site') === 'cross-site' || !mesmaOrigem)) {
    return NextResponse.json({ erro: 'Abra o painel para registrar a observacao.' }, { status: 403 });
  }
  const interna = process.env.AUTOMACAO_EXECUTION_KEY;
  if (!interna) return NextResponse.json({ erro: 'Integracao nao configurada.' }, { status: 503 });
  if (Number(request.headers.get('content-length') || 0) > 16 * 1024 * 1024) return NextResponse.json({ erro: 'Anexos excedem 15 MB.' }, { status: 413 });
  try {
    const headers: Record<string, string> = { 'X-Automation-Key': interna };
    if (['POST', 'PUT'].includes(request.method)) headers['Content-Type'] = request.headers.get('content-type') || '';
    const body = ['POST', 'PUT'].includes(request.method) ? await request.arrayBuffer() : undefined;
    if (body && body.byteLength > 16 * 1024 * 1024) return NextResponse.json({ erro: 'Anexos excedem 15 MB.' }, { status: 413 });
    const r = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:5000'}/api/historico/${caminho}${request.nextUrl.search}`, { method: request.method, headers, body, cache: 'no-store' });
    return new NextResponse(await r.arrayBuffer(), { status: r.status, headers: { 'Content-Type': r.headers.get('content-type') || 'application/json', 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff' } });
  } catch { return NextResponse.json({ erro: 'Nao foi possivel conectar ao servidor. Tente novamente.' }, { status: 502 }); }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
