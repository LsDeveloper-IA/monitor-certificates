'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Building2, CheckCircle2, Clock3,
  FileJson, Moon, Play, RefreshCw, Search, Square, Sun, XCircle,
} from 'lucide-react';

interface EmpresaResultado { cnpj: string; nome: string; motivo?: string }
interface Relatorio {
  titulo?: string;
  executado_em?: string;
  resumo: { certas?: number; sucessos?: number; ignorados?: number; falhas?: number; sem_certificado?: number; total_processado?: number };
  fonte_total?: 'sieg_cnpj_ativos' | 'relatorios';
  base_atualizada_em?: string;
  empresas_com_falha: EmpresaResultado[];
  empresas_com_sucesso?: EmpresaResultado[];
  empresas_certas?: EmpresaResultado[];
  empresas_corretas?: EmpresaResultado[];
  empresas_sem_certificado?: EmpresaResultado[];
  empresas_sem_resultado?: EmpresaResultado[];
  empresas_ignoradas?: EmpresaResultado[];
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
  automacoes?: Record<string, {
    nome: string;
    estado?: 'aguardando' | 'executando' | 'concluida' | 'falhou' | 'interrompida';
    codigo_saida?: number | null;
    logs: string[];
  }>;
}

export default function CertificadosVencidos() {
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [busca, setBusca] = useState('');
  const [modoEscuro, setModoEscuro] = useState(false);
  const [resultadoAtivo, setResultadoAtivo] = useState<'falhas' | 'sucessos' | 'sem_certificado' | 'sem_resultado'>('sem_certificado');
  const [executandoAutomacao, setExecutandoAutomacao] = useState(false);
  const [mensagemAutomacao, setMensagemAutomacao] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null);
  const [statusAutomacao, setStatusAutomacao] = useState<StatusAutomacao>({ executando: false, estado: 'aguardando', logs: [] });
  const estavaExecutando = useRef(false);

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
  }, [carregar]);

  const carregarStatusAutomacao = useCallback(async () => {
    if (document.visibilityState === 'hidden') return;
    try {
      const chaveAdmin = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO)?.trim() || '';
      const resposta = await fetch('/api/automacao/sieg-status', {
        headers: chaveAdmin ? { 'X-Admin-Key': chaveAdmin } : {},
        cache: 'no-store',
      });
      if (resposta.ok) {
        const novoStatus: StatusAutomacao = await resposta.json();
        const terminouAgora = estavaExecutando.current && !novoStatus.executando;
        estavaExecutando.current = novoStatus.executando;
        setStatusAutomacao(novoStatus);
        if (terminouAgora) await carregar();
      }
    } catch {
      // O status não deve impedir a leitura do relatório.
    }
  }, [carregar]);

  useEffect(() => {
    carregarStatusAutomacao();
    const intervalo = window.setInterval(
      carregarStatusAutomacao,
      statusAutomacao.executando ? 1500 : 10000,
    );
    return () => window.clearInterval(intervalo);
  }, [carregarStatusAutomacao, statusAutomacao.executando]);

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

      const resposta = await fetch('/api/automacao/sieg-executar', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          atualizar_excel: true,
          notificacoes_teste: false,
        }),
      });

      const conteudo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(conteudo?.erro || 'Falha ao iniciar as automações.');
      }

      setMensagemAutomacao({
        tipo: 'success',
        texto: 'As duas automações foram iniciadas em segundo plano.',
      });
      window.dispatchEvent(new Event('certificados-monitor:automacao-alterada'));
      await carregarStatusAutomacao();
    } catch (erro) {
      setMensagemAutomacao({
        tipo: 'error',
        texto: erro instanceof Error ? erro.message : 'Falha ao iniciar as automações.',
      });
    } finally {
      setExecutandoAutomacao(false);
    }
  }, [carregarStatusAutomacao]);

  const pararAutomacaoSieg = useCallback(async () => {
    try {
      const chaveAdmin = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO)?.trim() || '';
      const resposta = await fetch('/api/automacao/sieg-parar', {
        method: 'POST',
        headers: chaveAdmin ? { 'X-Admin-Key': chaveAdmin } : {},
      });
      const conteudo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) throw new Error(conteudo?.erro || 'Não foi possível parar as automações.');
      setMensagemAutomacao({ tipo: 'success', texto: 'As duas automações foram interrompidas.' });
      await carregarStatusAutomacao();
    } catch (erro) {
      setMensagemAutomacao({ tipo: 'error', texto: erro instanceof Error ? erro.message : 'Falha ao parar as automações.' });
    }
  }, [carregarStatusAutomacao]);

  const alternarTema = () => {
    const novo = !modoEscuro; setModoEscuro(novo);
    document.documentElement.classList.toggle('dark', novo);
    localStorage.setItem('tema', novo ? 'escuro' : 'claro');
  };

  const resumo = relatorio?.resumo || {};
  const listaSucessos = useMemo(() => relatorio?.empresas_com_sucesso ||
    relatorio?.empresas_certas || relatorio?.empresas_corretas || [], [relatorio]);
  const sucessos = listaSucessos.length;
  const ignorados = relatorio?.empresas_ignoradas?.length || 0;
  const falhas = relatorio?.empresas_com_falha?.length || 0;
  const listaSemCertificado = useMemo(
    () => relatorio?.empresas_sem_certificado || [],
    [relatorio],
  );
  const semCertificado = listaSemCertificado.length;
  const listaSemResultado = useMemo(() => relatorio?.empresas_sem_resultado || [], [relatorio]);
  const semResultado = listaSemResultado.length;
  const totalComResultado = sucessos + ignorados + falhas + semCertificado;
  const total = Number(resumo.total_processado ?? (totalComResultado + semResultado));
  const baseSieg = relatorio?.fonte_total === 'sieg_cnpj_ativos';
  const percentualFalhas = total ? Math.round((falhas / total) * 100) : 0;
  const percentualSucessos = total ? Math.round((sucessos / total) * 100) : 0;
  const percentualIgnorados = total ? Math.round((ignorados / total) * 100) : 0;
  const percentualSemCertificado = total ? Math.round((semCertificado / total) * 100) : 0;
  const percentualSemResultado = total ? Math.round((semResultado / total) * 100) : 0;
  const limitesGrafico = [sucessos, sucessos + ignorados, sucessos + ignorados + falhas,
    totalComResultado].map((numero) => total ? numero / total * 100 : 0);
  const empresas = useMemo(() => {
    const listas = {
      falhas: relatorio?.empresas_com_falha || [],
      sucessos: listaSucessos,
      sem_certificado: listaSemCertificado,
      sem_resultado: listaSemResultado,
    };
    const listaAtiva = listas[resultadoAtivo];
    const termo = busca.trim().toLocaleLowerCase('pt-BR');
    const numeros = busca.replace(/\D/g, '');
    if (!termo) return listaAtiva;
    return listaAtiva.filter((item) =>
      item.nome?.toLocaleLowerCase('pt-BR').includes(termo) ||
      Boolean(numeros && item.cnpj?.replace(/\D/g, '').includes(numeros)) ||
      item.motivo?.toLocaleLowerCase('pt-BR').includes(termo));
  }, [busca, listaSemCertificado, listaSemResultado, listaSucessos, relatorio, resultadoAtivo]);

  const cards = [
    { label: 'Total processado', valor: total, Icone: Building2, fundo: 'bg-blue-100', texto: 'text-blue-600' },
    { label: 'Sucessos', valor: sucessos, Icone: CheckCircle2, fundo: 'bg-green-100', texto: 'text-green-600' },
    { label: 'Sem resultado', valor: semResultado, Icone: Clock3, fundo: 'bg-gray-100', texto: 'text-gray-600' },
    { label: 'Falhas', valor: falhas, Icone: XCircle, fundo: 'bg-red-100', texto: 'text-red-600' },
    { label: 'Sem certificado', valor: semCertificado, Icone: AlertTriangle, fundo: 'bg-orange-100', texto: 'text-orange-600' },
  ];

  return <div className="min-h-screen bg-gray-50">
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8 min-h-16 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/" className="p-2 text-gray-500 hover:text-blue-600" aria-label="Voltar">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <FileJson className="w-7 h-7 text-red-600 shrink-0" />
          <h1 className="text-xl font-semibold text-gray-900 truncate">Automação de certificados vencidos</h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            onClick={executarAutomacaoSieg}
            disabled={executandoAutomacao || statusAutomacao.executando}
            className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {executandoAutomacao ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {executandoAutomacao ? 'Iniciando...' : statusAutomacao.executando ? 'Em execução' : 'Iniciar automação'}
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
        <div aria-live="polite" className={`mb-6 rounded-lg border p-4 flex gap-3 ${mensagemAutomacao.tipo === 'success' ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div className="text-sm font-medium">{mensagemAutomacao.texto}</div>
        </div>
      )}

      {statusAutomacao.executando && <section className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-900">
        <div className="flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <p className="font-medium">Automações em execução</p>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Object.entries(statusAutomacao.automacoes || {}).map(([id, automacao]) => (
            <div key={id} className="min-w-0 rounded-xl border border-blue-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-gray-800">{automacao.nome}</p>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                  automacao.estado === 'concluida' ? 'bg-green-100 text-green-700' :
                    automacao.estado === 'falhou' ? 'bg-red-100 text-red-700' :
                      automacao.estado === 'interrompida' ? 'bg-orange-100 text-orange-700' :
                        automacao.estado === 'executando' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-600'
                }`}>{automacao.estado === 'concluida' ? 'Concluída' : automacao.estado === 'falhou' ? 'Falhou' : automacao.estado === 'interrompida' ? 'Interrompida' : automacao.estado === 'executando' ? 'Executando' : 'Aguardando'}</span>
              </div>
              <pre className="h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
                {automacao.logs.length ? automacao.logs.slice(-30).join('\n') : 'Aguardando início...'}
              </pre>
            </div>
          ))}
        </div>
      </section>}

      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">{relatorio?.titulo || 'Resumo da automação de certificados'}</h2>
        <p className="text-sm text-gray-500 mt-1">
          {relatorio?.executado_em ? `Executado em ${new Date(relatorio.executado_em).toLocaleString('pt-BR')}` : 'Aguardando dados do Drive'}
          {relatorio?.arquivo_drive?.nome && ` • ${relatorio.arquivo_drive.nome}`}
        </p>
        {relatorio?.historico?.acumulado && <p className="mt-1 text-xs text-blue-600">
          Histórico acumulado • {relatorio.historico.arquivos_processados || 0} versão(ões) processada(s) • {relatorio.historico.empresas_acompanhadas || 0} empresa(s) identificada(s)
        </p>}
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5 mb-6">
        {cards.map(({ label, valor, Icone, fundo, texto }) => <div key={label} className="bg-white rounded-lg shadow p-5 flex items-center">
          <div className={`p-2 rounded-lg ${fundo}`}><Icone className={`w-6 h-6 ${texto}`} /></div>
          <div className="ml-4"><p className="text-sm text-gray-600">{label}</p><p className="text-2xl font-semibold text-gray-900">{valor}</p></div>
        </div>)}
      </section>

      {relatorio && <p className="mb-6 text-sm text-gray-600">
        {baseSieg
          ? 'Total de CNPJs únicos com “Ativo na Sieg” marcado. CPFs e documentos incompletos ficam fora da contagem.'
          : 'Total de CNPJs únicos identificados nos relatórios. A lista completa do SIEG estará disponível após uma execução completa da Auto_NC.'}
        {baseSieg && relatorio.base_atualizada_em && ` Base consultada em ${new Date(relatorio.base_atualizada_em).toLocaleString('pt-BR')}.`}
      </p>}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-5">Distribuição de todos os CNPJs ativos</h3>
          <div className="flex items-center justify-center">
            <div
              className="relative w-40 h-40 rounded-full"
              style={{
                background: total ? `conic-gradient(
                  #16a34a 0 ${limitesGrafico[0]}%,
                  #eab308 ${limitesGrafico[0]}% ${limitesGrafico[1]}%,
                  #dc2626 ${limitesGrafico[1]}% ${limitesGrafico[2]}%,
                  #f97316 ${limitesGrafico[2]}% ${limitesGrafico[3]}%,
                  #9ca3af ${limitesGrafico[3]}% 100%
                )` : '#e5e7eb',
              }}
            >
              <div className="absolute inset-4 bg-white rounded-full flex flex-col items-center justify-center">
                <span className="text-3xl font-bold text-gray-900">{total}</span>
                <span className="text-xs text-gray-500">{baseSieg ? 'CNPJs ativos únicos' : 'CNPJs únicos'}</span>
              </div>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2 text-center text-xs">
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-green-600" /><span className="text-gray-600">{percentualSucessos}% sucesso</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-yellow-500" /><span className="text-gray-600">{percentualIgnorados}% ignorado</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-red-600" /><span className="text-gray-600">{percentualFalhas}% falha</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-orange-500" /><span className="text-gray-600">{percentualSemCertificado}% sem certificado</span></div>
            <div><span className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full bg-gray-400" /><span className="text-gray-600">{percentualSemResultado}% sem resultado</span></div>
          </div>
        </div>
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h3 className="font-medium text-gray-900 mb-5">Resultado da execução</h3>
          {[['Sucessos', sucessos, 'bg-green-500'], ['Falhas', falhas, 'bg-red-500'], ['Sem certificado', semCertificado, 'bg-orange-500'], ['Sem resultado', semResultado, 'bg-gray-400'], ...(ignorados > 0 ? [['Ignorados', ignorados, 'bg-yellow-500']] : [])].map(([nome, valor, cor]) => {
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
              <p className="text-sm text-gray-500">{resultadoAtivo === 'sem_resultado'
                ? 'Empresas ativas no SIEG ainda sem correspondência nas demais categorias, após comparar CNPJ e nome.'
                : 'Dados nominais disponíveis nos relatórios das automações.'}</p>
            </div>
            <div className="relative"><Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" /><input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar empresa, CNPJ ou resultado" className="w-full sm:w-72 pl-10 pr-4 py-2 border border-gray-300 rounded-lg" /></div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Resultado das empresas">
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
            <button
              onClick={() => { setResultadoAtivo('sem_certificado'); setBusca(''); }}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${resultadoAtivo === 'sem_certificado' ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              role="tab"
              aria-selected={resultadoAtivo === 'sem_certificado'}
            >
              Sem certificado ({semCertificado})
            </button>
            <button
              onClick={() => { setResultadoAtivo('sem_resultado'); setBusca(''); }}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${resultadoAtivo === 'sem_resultado' ? 'bg-gray-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              role="tab"
              aria-selected={resultadoAtivo === 'sem_resultado'}
            >
              Sem resultado ({semResultado})
            </button>
          </div>
        </div>
        <div className="overflow-x-auto"><table className="w-full divide-y divide-gray-200"><thead className="bg-gray-50"><tr><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Empresa</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">CNPJ</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resultado</th></tr></thead>
          <tbody className="divide-y divide-gray-200">{empresas.map((item, indice) => <tr key={`${item.cnpj}-${indice}`} className="hover:bg-gray-50"><td className="px-6 py-4 text-sm font-medium text-gray-900">{item.nome || 'Não informada'}</td><td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">{formatarCnpj(item.cnpj)}</td><td className={`px-6 py-4 text-sm ${resultadoAtivo === 'falhas' ? 'text-red-700' : resultadoAtivo === 'sem_certificado' ? 'text-orange-700' : 'text-green-700'}`}>
            {resultadoAtivo === 'falhas'
              ? <span className="inline-flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />{item.motivo || 'Motivo não informado'}</span>
              : resultadoAtivo === 'sem_certificado'
                ? <span className="inline-flex gap-2 font-medium"><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />Sem certificado cadastrado</span>
              : resultadoAtivo === 'sem_resultado'
                ? <span className="inline-flex gap-2 font-medium text-gray-600"><Clock3 className="w-4 h-4 shrink-0 mt-0.5" />Sem resultado nos relatórios</span>
              : <span className="inline-flex gap-2 font-medium"><CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />Processada com sucesso</span>}
          </td></tr>)}</tbody>
        </table></div>
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'falhas' && <p className="p-8 text-center text-gray-500">Nenhuma empresa com falha encontrada.</p>}
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'sucessos' && <div className="p-8 text-center">
          <CheckCircle2 className="mx-auto mb-3 h-8 w-8 text-green-500" />
          <p className="font-medium text-gray-900">Nenhuma empresa processada com sucesso foi registrada neste relatório.</p>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-500">As empresas só aparecem aqui quando a automação SIEG conclui o processamento e grava a lista nominal.</p>
        </div>}
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'sem_certificado' && <p className="p-8 text-center text-gray-500">Nenhuma empresa sem certificado foi identificada pela Auto_NC.</p>}
        {!carregando && !empresas.length && !erro && resultadoAtivo === 'sem_resultado' && <p className="p-8 text-center text-gray-500">Nenhuma empresa sem resultado encontrada.</p>}
      </section>
    </main>
  </div>;
}
