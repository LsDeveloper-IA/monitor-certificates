'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Building2, CheckCircle2, Clock3,
  FileJson, Moon, Play, RefreshCw, Search, Square, Sun, XCircle,
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
  historico?: { acumulado?: boolean; arquivos_processados?: number; empresas_acompanhadas?: number };
}

function formatarCnpj(valor: string) {
  const numeros = String(valor || '').replace(/\D/g, '');
  if (numeros.length !== 14) return valor || 'Não informado';
  return numeros.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
}

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';
interface StatusAutomacao {
  executando: boolean;
  estado: string;
  logs: string[];
  erro?: string | null;
}

export default function CertificadosVencidos() {
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [busca, setBusca] = useState('');
  const [modoEscuro, setModoEscuro] = useState(false);
  const [resultadoAtivo, setResultadoAtivo] = useState<'falhas' | 'sucessos'>('falhas');
  const [executandoAutomacao, setExecutandoAutomacao] = useState(false);
  const [mensagemAutomacao, setMensagemAutomacao] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null);
  const [statusAutomacao, setStatusAutomacao] = useState<StatusAutomacao>({ executando: false, estado: 'aguardando', logs: [] });

  const carregar = useCallback(async () => {
    setCarregando(true); setErro('');
    try {
      const resposta = await fetch('/api/relatorios/certificados-vencidos', { cache: 'no-store' });
      const tipoConteudo = resposta.headers.get('content-type') || '';
      const conteudo = tipoConteudo.includes('application/json')
        ? await resposta.json()
        : {
          erro: resposta.status >= 500
            ? 'O servidor backend está indisponível. Inicie o serviço na porta 5000.'
            : 'O servidor retornou uma resposta inválida.'
        };
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
    const intervalo = window.setInterval(carregar, 30000);
    return () => window.clearInterval(intervalo);
  }, [carregar]);

  const carregarStatusAutomacao = useCallback(async () => {
    try {
      const resposta = await fetch('/api/automacao/status', { cache: 'no-store' });
      if (resposta.ok) setStatusAutomacao(await resposta.json());
    } catch {
      // O status não deve impedir a leitura do relatório.
    }
  }, []);

  useEffect(() => {
    carregarStatusAutomacao();
    const intervalo = window.setInterval(carregarStatusAutomacao, 2000);
    return () => window.clearInterval(intervalo);
  }, [carregarStatusAutomacao]);

  const executarAutomacaoSieg = useCallback(async () => {
    const chaveAdmin = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO)?.trim() || '';

    setExecutandoAutomacao(true);
    setMensagemAutomacao(null);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (chaveAdmin) {
        headers['X-Admin-Key'] = chaveAdmin;
      }

      const resposta = await fetch('/api/automacao/executar', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          atualizar_excel: true,
          notificacoes_teste: false,
        }),
      });

      const conteudo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(conteudo?.erro || 'Falha ao iniciar a automação SIEG.');
      }

      setMensagemAutomacao({
        tipo: 'success',
        texto: 'Automação SIEG iniciada em segundo plano.',
      });
      window.dispatchEvent(new Event('certificados-monitor:automacao-alterada'));
      setTimeout(() => carregar(), 1500);
    } catch (erro) {
      setMensagemAutomacao({
        tipo: 'error',
        texto: erro instanceof Error ? erro.message : 'Falha ao iniciar a automação SIEG.',
      });
    } finally {
      setExecutandoAutomacao(false);
    }
  }, [carregar]);

  const pararAutomacaoSieg = useCallback(async () => {
    try {
      const resposta = await fetch('/api/automacao/parar', { method: 'POST' });
      const conteudo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) throw new Error(conteudo?.erro || 'Não foi possível parar a automação SIEG.');
      setMensagemAutomacao({ tipo: 'success', texto: 'Automação SIEG interrompida.' });
      await carregarStatusAutomacao();
    } catch (erro) {
      setMensagemAutomacao({ tipo: 'error', texto: erro instanceof Error ? erro.message : 'Falha ao parar a automação SIEG.' });
    }
  }, [carregarStatusAutomacao]);

  const alternarTema = () => {
    const novo = !modoEscuro; setModoEscuro(novo);
    document.documentElement.classList.toggle('dark', novo);
    localStorage.setItem('tema', novo ? 'escuro' : 'claro');
  };

  const resumo = relatorio?.resumo || {};
  const listaSucessos = relatorio?.empresas_com_sucesso ||
    relatorio?.empresas_certas || relatorio?.empresas_corretas || [];
  const sucessos = Number(resumo.sucessos ?? listaSucessos.length);
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
          <button
            type="button"
            onClick={executarAutomacaoSieg}
            disabled={executandoAutomacao}
            className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {executandoAutomacao ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {executandoAutomacao ? 'Executando...' : 'Automação SIEG'}
          </button>
          {statusAutomacao.executando && <button
            type="button"
            onClick={pararAutomacaoSieg}
            className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
          >
            <Square className="w-4 h-4" /> Parar
          </button>}
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

      {mensagemAutomacao && (
        <div className={`mb-6 rounded-lg border p-4 flex gap-3 ${mensagemAutomacao.tipo === 'success' ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div className="text-sm font-medium">{mensagemAutomacao.texto}</div>
        </div>
      )}

      {statusAutomacao.executando && <section className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-900">
        <div className="flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <p className="font-medium">Automação SIEG em execução</p>
        </div>
        <p className="mt-2 text-sm">{statusAutomacao.logs.at(-1) || 'Iniciando automação...'}</p>
      </section>}

      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">{relatorio?.titulo || 'Resumo da automação SIEG'}</h2>
        <p className="text-sm text-gray-500 mt-1">
          {relatorio?.executado_em ? `Executado em ${new Date(relatorio.executado_em).toLocaleString('pt-BR')}` : 'Aguardando dados do Drive'}
          {relatorio?.arquivo_drive?.nome && ` • ${relatorio.arquivo_drive.nome}`}
        </p>
        {relatorio?.historico?.acumulado && <p className="mt-1 text-xs text-blue-600">
          Histórico acumulado • {relatorio.historico.arquivos_processados || 0} versão(ões) processada(s) • {relatorio.historico.empresas_acompanhadas || 0} empresa(s) identificada(s)
        </p>}
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
          <p className="font-medium text-gray-900">Nenhuma empresa processada com sucesso foi registrada neste relatório.</p>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-500">As empresas só aparecem aqui quando a automação SIEG conclui o processamento e grava a lista nominal.</p>
        </div>}
      </section>
    </main>
  </div>;
}
