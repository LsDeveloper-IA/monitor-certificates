import { NextResponse } from 'next/server';

const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';

export async function GET() {
  try {
    const resposta = await fetch(`${backendUrl}/api/relatorios/certificados-vencidos`, {
      cache: 'no-store',
    });
    const relatorio = await resposta.json();
    if (!resposta.ok) return NextResponse.json(relatorio, { status: resposta.status });

    // O backend consolida as quatro categorias e calcula o total por empresa.
    return NextResponse.json(relatorio);
  } catch {
    return NextResponse.json(
      { erro: 'Não foi possível carregar o relatório das automações.' },
      { status: 502 },
    );
  }
}
