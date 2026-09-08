import { readFile } from 'fs/promises';
import path from 'path';
import { NextResponse } from 'next/server';

const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';

interface EmpresaSemCertificado {
  nome?: string;
  cnpj?: string;
  motivo?: string;
}

async function carregarEmpresasSemCertificado() {
  const arquivo = path.resolve(
    process.cwd(),
    '..',
    'Auto_NC',
    'empresas_sem_certificado.json',
  );
  try {
    const conteudo = JSON.parse(await readFile(arquivo, 'utf-8'));
    if (!Array.isArray(conteudo.empresas)) return [];

    const unicas = new Map<string, EmpresaSemCertificado>();
    for (const empresa of conteudo.empresas as EmpresaSemCertificado[]) {
      const nome = String(empresa.nome || '').trim();
      const cnpj = String(empresa.cnpj || '').replace(/\D/g, '');
      if (!nome && !cnpj) continue;
      unicas.set(cnpj || nome.toLocaleLowerCase('pt-BR'), {
        nome: nome || 'Empresa não informada',
        cnpj,
        motivo: empresa.motivo || 'Empresa sem certificado cadastrado no SIEG',
      });
    }
    return [...unicas.values()];
  } catch {
    return [];
  }
}

export async function GET() {
  try {
    const resposta = await fetch(`${backendUrl}/api/relatorios/certificados-vencidos`, {
      cache: 'no-store',
    });
    const relatorio = await resposta.json();
    if (!resposta.ok) return NextResponse.json(relatorio, { status: resposta.status });

    const empresas = await carregarEmpresasSemCertificado();
    relatorio.empresas_sem_certificado = empresas;
    relatorio.resumo = {
      ...(relatorio.resumo || {}),
      sem_certificado: empresas.length,
    };
    return NextResponse.json(relatorio);
  } catch {
    return NextResponse.json(
      { erro: 'Não foi possível carregar o relatório das automações.' },
      { status: 502 },
    );
  }
}
