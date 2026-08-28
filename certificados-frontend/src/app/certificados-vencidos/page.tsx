'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Building2, CheckCircle2, Clock3,
  FileJson, Moon, RefreshCw, Search, Sun, XCircle,
} from 'lucide-react';

interface EmpresaResultado { cnpj: string; nome: string; motivo?: string }
interface Relatorio {
  titulo?: string;
  executado_em?: string;
  resumo: { certas?: number; sucessos?: number; ignorados?: number; falhas?: number };
  empresas_com_falha: EmpresaResultado[];
  empresas_com_sucesso?: EmpresaResultado[];
  empresas_certas?: EmpresaResultado[];
  empresas_corretas?: EmpresaResultado[];
  arquivo_drive?: { nome?: string; modificado_em?: string };
}

function formatarCnpj(valor: string) {
  const numeros = String(valor || '').replace(/\D/g, '');
  if (numeros.length !== 14) return valor || 'Não informado';
  return numeros.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
}

export default function CertificadosVencidos() {
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [busca, setBusca] = useState('');
  const [modoEscuro, setModoEscuro] = useState(false);
  const [resultadoAtivo, setResultadoAtivo] = useState<'falhas' | 'sucessos'>('falhas');

  const carregar = useCallback(async () => {
    setCarregando(true); setErro('');
    try {
      const resposta = await fetch('/api/relatorios/certificados-vencidos', { cache: 'no-store' });
      const tipoConteudo = resposta.headers.get('content-type') || '';
      const conteudo = tipoConteudo.includes('application/json')
        ? await resposta.json()
        : { erro: resposta.status >= 500
          ? 'O servidor backend está indisponível. Inicie o serviço na porta 5000.'
          : 'O servidor retornou uma resposta inválida.' };
      if (!resposta.ok) throw new Error(conteudo.erro || 'Falha ao carregar o relatório.');
      setRelatorio(conteudo);
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Falha ao carregar o relatório.');
    } finally { setCarregando(false); }
  }, []);

  useEffect(() => {
    const escuro = localStorage.getItem('tema') === 'escuro';
    setModoEscuro(escuro); document.documentElement.classList.toggle('dark', escuro);
    carregar();
  }, [carregar]);

  const alternarTema = () => {
    const novo = !modoEscuro; setModoEscuro(novo);
    document.documentElement.classList.toggle('dark', novo);
    localStorage.setItem('tema', novo ? 'escuro' : 'claro');
  };

  const resumo = relatorio?.resumo || {};
  const listaSucessos = relatorio?.empresas_com_sucesso ||
    relatorio?.empresas_certas || relatorio?.empresas_corretas || [];
  const sucessos = Number(resumo.certas ?? resumo.sucessos ?? listaSucessos.length);
  const ignorados = Number(resumo.ignorados || 0);
  const falhas = Number(resumo.falhas ?? relatorio?.empresas_com_falha.length ?? 0);
  const total = sucessos + ignorados + falhas;
  const percentualFalhas = total ? Math.round((falhas / total) * 100) : 0;
  const percentualSucessos = total ? Math.round((sucessos / total) * 100) : 0;
  const percentualIgnorados = total ? Math.round((ignorados / total) * 100) : 0;
  const listaAtiva = resultadoAtivo === 'falhas'
    ? (relatorio?.empresas_com_falha || [])
    : listaSucessos;
  const empresas = useMemo(() => listaAtiva.filter((item) => {
    const termo = busca.toLocaleLowerCase('pt-BR');
    return item.nome?.toLocaleLowerCase('pt-BR').includes(termo) || item.cnpj?.includes(busca) ||
      item.motivo?.toLocaleLowerCase('pt-BR').includes(termo);
  }), [listaAtiva, busca]);

  const cards = [
    { label: 'Total processado', valor: total, Icone: Building2, fundo: 'bg-blue-100', texto: 'text-blue-600' },
    { label: 'Sucessos', valor: sucessos, Icone: CheckCircle2, fundo: 'bg-green-100', texto: 'text-green-600' },
    { label: 'Ignorados', valor: ignorados, Icone: Clock3, fundo: 'bg-yellow-100', texto: 'text-yellow-600' },
    { label: 'Falhas', valor: falhas, Icone: XCircle, fundo: 'bg-red-100', texto: 'text-red-600' },
  ];

  return <div className="min-h-screen bg-gray-50">
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/" className="p-2 text-gray-500 hover:text-blue-600" aria-label="Voltar">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FileJson className="w-7 h-7 text-red-600 shrink-0" />
          <h1 className="text-xl font-semibold text-gray-900 truncate">Certificados vencidos</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={carregar} className="p-2 text-gray-500 hover:text-blue-600" title="Atualizar">
            <RefreshCw className={`w-5 h-5 ${carregando ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={alternarTema} className="p-2 text-gray-500 hover:text-gray-700" aria-label="Alternar tema">
            {modoEscuro ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </div>
    </header>

    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {erro && <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 flex gap-3">
        <AlertTriangle className="w-5 h-5 shrink-0" /><div><p className="font-medium">Não foi possível abrir o relatório</p><p className="text-sm mt-1">{erro}</p></div>
      </div>}

      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">{relatorio?.titulo || 'Resumo da automação SIEG'}</h2>
        <p className="text-sm text-gray-500 mt-1">
          {relatorio?.executado_em ? `Executado em ${new Date(relatorio.executado_em).toLocaleString('pt-BR')}` : 'Aguardando dados do Drive'}
          {relatorio?.arquivo_drive?.nome && ` • ${relatorio.arquivo_drive.nome}`}
        </p>
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
        {cards.map(({ label, valor, Icone, fundo, texto }) => <div key={label} className="bg-white rounded-lg shadow p-5 flex items-center">
          <div className={`p-2 rounded-lg ${fundo}`}><Icone className={`w-6 h-6 ${texto}`} /></div>
          <div className="ml-4"><p className="text-sm text-gray-600">{label}</p><p className="text-2xl font-semibold text-gray-900">{valor}</p></div>
        </div>)}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-5">Distribuição geral</h3>
          <div className="flex items-center justify-center">
            <div
              className="relative w-40 h-40 rounded-full"
              style={{
                background: `conic-gradient(
                  #16a34a 0 ${percentualSucessos}%,
                  #eab308 ${percentualSucessos}% ${percentualSucessos + percentualIgnorados}%,
                  #dc2626 ${percentualSucessos + percentualIgnorados}% 100%
                )`,
              }}
            >
              <div className="absolute inset-4 bg-white rounded-full flex flex-col items-center justify-center">
                <span className="text-3xl font-bold text-gray-900">{total}</span>
                <span className="text-xs text-gray-500">processadas</span>
              </div>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center text-xs">
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-green-600" /><span className="text-gray-600">{percentualSucessos}% sucesso</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-yellow-500" /><span className="text-gray-600">{percentualIgnorados}% ignorado</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-red-600" /><span className="text-gray-600">{percentualFalhas}% falha</span></div>
          </div>
        </div>
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-5">Resultado da execução</h3>
          {[['Sucessos', sucessos, 'bg-green-500'], ['Ignorados', ignorados, 'bg-yellow-500'], ['Falhas', falhas, 'bg-red-500']].map(([nome, valor, cor]) => {
            const numero = Number(valor); const largura = total ? (numero / total) * 100 : 0;
            return <div key={String(nome)} className="mb-5 last:mb-0"><div className="flex justify-between text-sm mb-2"><span className="text-gray-600">{nome}</span><b className="text-gray-900">{numero}</b></div><div className="h-3 bg-gray-100 rounded-full overflow-hidden"><div className={`h-full ${cor} rounded-full`} style={{ width: `${largura}%` }} /></div></div>;
          })}
        </div>
      </section>

      <section className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Empresas por resultado</h3>
              <p className="text-sm text-gray-500">Dados nominais disponíveis no último relatório</p>
            </div>
            <div className="relative"><Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" /><input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar empresa, CNPJ ou resultado" className="w-full sm:w-72 pl-10 pr-4 py-2 border border-gray-300 rounded-lg" /></div>
          </div>
          <div className="mt-5 flex gap-2" role="tablist" aria-label="Resultado das empresas">
            <button
              onClick={() => { setResultadoAtivo('falhas'); setBusca(''); }}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${resultadoAtivo === 'falhas' ? 'bg-red-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              role="tab"
              aria-selected={resultadoAtivo === 'falhas'}
            >
              Com falha ({falhas})
            </button>
            <button
              onClick={() => { setResultadoAtivo('sucessos'); setBusca(''); }}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${resultadoAtivo === 'sucessos' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              role="tab"
              aria-selected={resultadoAtivo === 'sucessos'}
            >
              Com sucesso ({sucessos})
            </button>
          </div>
        </div>
        <div className="overflow-x-auto"><table className="w-full divide-y divide-gray-200"><thead className="bg-gray-50"><tr><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Empresa</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">CNPJ</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resultado</th></tr></thead>
          <tbody className="divide-y divide-gray-200">{empresas.map((item, indice) => <tr key={`${item.cnpj}-${indice}`} className="hover:bg-gray-50"><td className="px-6 py-4 text-sm font-medium text-gray-900">{item.nome || 'Não informada'}</td><td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">{formatarCnpj(item.cnpj)}</td><td className={`px-6 py-4 text-sm ${resultadoAtivo === 'falhas' ? 'text-red-700' : 'text-green-700'}`}>
            {resultadoAtivo === 'falhas'
              ? <span className="inline-flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />{item.motivo || 'Motivo não informado'}</span>
              : <span className="inline-flex gap-2 font-medium"><CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />Processada com sucesso</span>}
          </td></tr>)}</tbody>
        </table></div>
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'falhas' && <p className="p-8 text-center text-gray-500">Nenhuma empresa com falha encontrada.</p>}
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'sucessos' && <div className="p-8 text-center">
          <CheckCircle2 className="mx-auto mb-3 h-8 w-8 text-green-500" />
          <p className="font-medium text-gray-900">O resumo informa {sucessos} empresas com sucesso.</p>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-500">Este arquivo ainda não inclui a lista nominal <code>empresas_com_sucesso</code>. Quando a automação adicionar essa lista ao JSON, as empresas aparecerão aqui automaticamente.</p>
        </div>}
      </section>
    </main>
  </div>;
}
