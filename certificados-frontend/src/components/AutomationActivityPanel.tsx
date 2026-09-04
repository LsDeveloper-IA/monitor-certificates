'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle, ChevronDown, Clock, Download, Mail, MessageCircle, RefreshCw, Search, XCircle } from 'lucide-react';
import IntegrationHealthPanel from '@/components/IntegrationHealthPanel';

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';

interface ResumoEnvios {
  email_enviados: number;
  email_duplicados: number;
  email_falhas: number;
  whatscontabil_enviados: number;
  whatscontabil_duplicados: number;
  whatscontabil_falhas: number;
  whatscontabil_interrompidos: number;
}

interface ExecucaoAutomacao {
  id: string | null;
  executando: boolean;
  estado: 'aguardando' | 'executando' | 'concluida' | 'falhou';
  inicio: string | null;
  fim: string | null;
  duracao_segundos: number | null;
  codigo_saida: number | null;
  erro: string | null;
  atualizou_excel: boolean;
  notificacoes_teste: boolean;
  escopo_notificacoes_teste?: 'nenhum' | 'relatorios' | 'clientes' | 'completo';
  forcou_reenvio_teste?: boolean;
  resumo_envios?: ResumoEnvios;
  logs?: string[];
  etapa?: string;
  progresso?: number;
}

interface MensagemHistorico {
  id: number | string;
  cnpj: string;
  arquivo: string;
  dias: number;
  vencimento: string;
  tipo: string;
  destinatario: string;
  enviado_em: string;
  status: 'enviado' | 'falhou' | 'duplicado' | 'interrompido';
  motivo: string;
}

const resumoVazio: ResumoEnvios = {
  email_enviados: 0,
  email_duplicados: 0,
  email_falhas: 0,
  whatscontabil_enviados: 0,
  whatscontabil_duplicados: 0,
  whatscontabil_falhas: 0,
  whatscontabil_interrompidos: 0,
};

function formatarDataHora(valor: string | null) {
  return valor ? new Date(valor).toLocaleString('pt-BR') : '--';
}

function formatarDuracao(total: number | null) {
  if (total === null) return '--';
  const minutos = Math.floor(total / 60);
  const segundos = total % 60;
  return minutos ? `${minutos}min ${segundos}s` : `${segundos}s`;
}

export default function AutomationActivityPanel() {
  const [status, setStatus] = useState<ExecucaoAutomacao | null>(null);
  const [historico, setHistorico] = useState<ExecucaoAutomacao[]>([]);
  const [historicoMensagens, setHistoricoMensagens] = useState<MensagemHistorico[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState('');
  const [buscaMensagem, setBuscaMensagem] = useState('');
  const [filtroResultado, setFiltroResultado] = useState('todos');
  const [filtroTipo, setFiltroTipo] = useState('todos');
  const [filtroPeriodo, setFiltroPeriodo] = useState('todos');
  const [execucaoExpandida, setExecucaoExpandida] = useState<string | null>(null);
  const [repetindoFalhas, setRepetindoFalhas] = useState(false);
  const [confirmarRepeticao, setConfirmarRepeticao] = useState(false);
  const [avisoAcao, setAvisoAcao] = useState('');

  const carregarAtividade = useCallback(async (mostrarCarregamento = false) => {
    const chaveAdmin = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO) || '';
    if (!chaveAdmin) {
      setErro('Informe a chave administrativa em Configurações para consultar a atividade.');
      setCarregando(false);
      return;
    }

    if (mostrarCarregamento) setCarregando(true);
    try {
      const cabecalhos = { 'X-Admin-Key': chaveAdmin };
      const [respostaStatus, respostaHistorico, respostaMensagens] = await Promise.all([
        fetch('/api/automacao/status', { headers: cabecalhos, cache: 'no-store' }),
        fetch('/api/automacao/historico', { headers: cabecalhos, cache: 'no-store' }),
        fetch('/api/automacao/historico-mensagens?limite=50', { headers: cabecalhos, cache: 'no-store' }),
      ]);

      if (!respostaStatus.ok || !respostaHistorico.ok || !respostaMensagens.ok) {
        throw new Error('Não foi possível consultar a atividade da automação.');
      }

      const novoStatus = await respostaStatus.json();
      const novoHistorico = await respostaHistorico.json();
      const novasMensagens = await respostaMensagens.json();
      setStatus(novoStatus);
      setHistorico(novoHistorico.execucoes || []);
      setHistoricoMensagens(novasMensagens.mensagens || []);
      setErro('');
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Falha ao consultar a atividade.');
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    carregarAtividade(true);
  }, [carregarAtividade]);

  useEffect(() => {
    const intervalo = window.setInterval(
      () => carregarAtividade(false),
      status?.executando ? 3000 : 15000,
    );
    return () => window.clearInterval(intervalo);
  }, [carregarAtividade, status?.executando]);

  const mensagensFiltradas = historicoMensagens.filter((mensagem) => {
    if (filtroResultado !== 'todos' && mensagem.status !== filtroResultado) return false;
    if (filtroTipo !== 'todos' && mensagem.tipo !== filtroTipo) return false;
    if (filtroPeriodo !== 'todos') {
      const dias = Number(filtroPeriodo);
      const limite = Date.now() - dias * 24 * 60 * 60 * 1000;
      if (new Date(mensagem.enviado_em).getTime() < limite) return false;
    }
    const termo = buscaMensagem.trim().toLocaleLowerCase('pt-BR');
    if (!termo) return true;
    return [mensagem.cnpj, mensagem.arquivo, mensagem.tipo, mensagem.motivo]
      .join(' ')
      .toLocaleLowerCase('pt-BR')
      .includes(termo);
  });

  const exportarHistorico = () => {
    const escapar = (valor: unknown) => `"${String(valor ?? '').replaceAll('"', '""')}"`;
    const linhas = [
      ['Data', 'Tipo', 'CNPJ', 'Arquivo', 'Dias', 'Destino', 'Resultado', 'Motivo'],
      ...mensagensFiltradas.map((item) => [
        formatarDataHora(item.enviado_em), item.tipo, item.cnpj, item.arquivo,
        item.dias, item.destinatario, item.status, item.motivo,
      ]),
    ];
    const conteudo = `\uFEFF${linhas.map((linha) => linha.map(escapar).join(';')).join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([conteudo], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `historico-mensagens-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const repetirSomenteFalhas = async () => {
    const chaveAdmin = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO) || '';
    if (!chaveAdmin || status?.executando) return;
    setRepetindoFalhas(true);
    setAvisoAcao('');
    try {
      const resposta = await fetch('/api/automacao/executar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Key': chaveAdmin },
        body: JSON.stringify({
          atualizar_excel: false,
          notificacoes_teste: true,
          escopo_notificacoes_teste: 'completo',
          forcar_reenvio_teste: false,
        }),
      });
      const conteudo = await resposta.json();
      if (!resposta.ok) throw new Error(conteudo.erro || 'Falha ao iniciar nova tentativa.');
      setAvisoAcao('Nova tentativa iniciada no numero de teste. Envios confirmados continuarao bloqueados.');
      setConfirmarRepeticao(false);
      await carregarAtividade(false);
    } catch (falha) {
      setAvisoAcao(falha instanceof Error ? falha.message : 'Falha ao repetir os envios.');
    } finally {
      setRepetindoFalhas(false);
    }
  };

  if (carregando) {
    return (
      <div className="space-y-4 p-5 sm:p-6">
        <div className="skeleton h-28 rounded-xl" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="skeleton h-28 rounded-xl" />
          <div className="skeleton h-28 rounded-xl" />
        </div>
      </div>
    );
  }

  if (erro) {
    return (
      <div className="p-6 text-center">
        <XCircle className="mx-auto h-10 w-10 text-red-500" />
        <p className="mt-3 font-medium text-gray-800">Atividade indisponível</p>
        <p className="mt-1 text-sm text-gray-500">{erro}</p>
        <button
          type="button"
          onClick={() => carregarAtividade(true)}
          className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!status) return null;
  const resumo = status.resumo_envios || resumoVazio;
  const progresso = Math.max(0, Math.min(100, status.progresso ?? 0));
  const etapaAtual = status.etapa || (status.executando ? 'Processando certificados' : 'Aguardando nova execucao');
  const IconeStatus = status.executando ? Activity : status.estado === 'concluida' ? CheckCircle : status.estado === 'falhou' ? XCircle : Clock;
  const corStatus = status.executando
    ? 'border-blue-200 bg-blue-50 text-blue-800'
    : status.estado === 'concluida'
      ? 'border-green-200 bg-green-50 text-green-800'
      : status.estado === 'falhou'
        ? 'border-red-200 bg-red-50 text-red-800'
        : 'border-gray-200 bg-gray-50 text-gray-700';

  return (
    <div className="space-y-5 p-5 sm:p-6">
      <section className={`rounded-xl border p-4 ${corStatus}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <IconeStatus className={`mt-0.5 h-5 w-5 ${status.executando ? 'animate-pulse' : ''}`} />
            <div>
              <p className="font-semibold">
                {status.executando ? 'Automação em andamento' : status.estado === 'concluida' ? 'Última execução concluída' : status.estado === 'falhou' ? 'Última execução falhou' : 'Aguardando execução'}
              </p>
              <p className="mt-1 text-xs opacity-80">
                Início: {formatarDataHora(status.inicio)} · duração: {formatarDuracao(status.duracao_segundos)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => carregarAtividade(true)}
            className="rounded-lg bg-white/70 p-2 hover:bg-white"
            aria-label="Atualizar atividade"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
        {status.executando && (
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-xs opacity-80">
              <span>{etapaAtual}</span><span>{progresso}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-blue-100">
              <div className="h-full rounded-full bg-blue-500 transition-all duration-500" style={{ width: `${progresso}%` }} />
            </div>
          </div>
        )}
        {status.erro && <p className="mt-3 text-sm">{status.erro}</p>}
      </section>

      <IntegrationHealthPanel embutido />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <section className="rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-blue-600" />
            <h4 className="font-semibold text-gray-900">E-mail</h4>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div><p className="text-xl font-semibold text-green-600">{resumo.email_enviados}</p><p className="text-gray-500">Enviados</p></div>
            <div><p className="text-xl font-semibold text-yellow-600">{resumo.email_duplicados}</p><p className="text-gray-500">Ignorados</p></div>
            <div><p className="text-xl font-semibold text-red-600">{resumo.email_falhas}</p><p className="text-gray-500">Falhas</p></div>
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-green-600" />
            <h4 className="font-semibold text-gray-900">WhatsContábil</h4>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
            <div><p className="text-xl font-semibold text-green-600">{resumo.whatscontabil_enviados}</p><p className="text-gray-500">Enviados</p></div>
            <div><p className="text-xl font-semibold text-yellow-600">{resumo.whatscontabil_duplicados}</p><p className="text-gray-500">Ignorados</p></div>
            <div><p className="text-xl font-semibold text-red-600">{resumo.whatscontabil_falhas}</p><p className="text-gray-500">Falhas</p></div>
            <div><p className="text-xl font-semibold text-orange-600">{resumo.whatscontabil_interrompidos}</p><p className="text-gray-500">Não tentados</p></div>
          </div>
        </section>
      </div>

      {(status.logs?.length || 0) > 0 && (
        <section>
          <h4 className="mb-2 font-semibold text-gray-900">Progresso recente</h4>
          <pre className="max-h-44 overflow-y-auto whitespace-pre-wrap rounded-xl bg-gray-900 p-4 text-xs text-gray-100">
            {status.logs!.slice(-12).join('\n')}
          </pre>
        </section>
      )}

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="font-semibold text-gray-900">Historico de mensagens</h4>
            <p className="mt-0.5 text-xs text-gray-500">{mensagensFiltradas.length} de {historicoMensagens.length} registros</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setConfirmarRepeticao(true)}
              disabled={repetindoFalhas || status.executando || !historicoMensagens.some((item) => item.status === 'falhou' || item.status === 'interrompido')}
              className="flex items-center rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              title="Executa novamente com a protecao de duplicidade ativa"
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${repetindoFalhas ? 'animate-spin' : ''}`} />
              Repetir falhas
            </button>
            <button
              type="button"
              onClick={exportarHistorico}
              disabled={mensagensFiltradas.length === 0}
              className="flex items-center rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <Download className="mr-1.5 h-3.5 w-3.5" /> Exportar CSV
            </button>
          </div>
        </div>
        {confirmarRepeticao && (
          <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
            <p className="font-semibold">Confirmar nova tentativa?</p>
            <p className="mt-1">O fluxo completo será executado somente no número de teste. A proteção contra duplicidade continuará ativa.</p>
            <div className="mt-3 flex gap-2">
              <button type="button" onClick={() => setConfirmarRepeticao(false)} className="rounded-lg bg-white px-3 py-1.5 font-medium text-gray-700">Cancelar</button>
              <button type="button" onClick={repetirSomenteFalhas} disabled={repetindoFalhas} className="rounded-lg bg-amber-600 px-3 py-1.5 font-medium text-white disabled:opacity-50">Confirmar teste</button>
            </div>
          </div>
        )}
        {avisoAcao && <p className="mb-3 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700">{avisoAcao}</p>}
        <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_160px_150px_130px]">
          <label className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="search"
              value={buscaMensagem}
              onChange={(evento) => setBuscaMensagem(evento.target.value)}
              placeholder="Buscar CNPJ, arquivo ou motivo"
              className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-xs"
            />
          </label>
          <select value={filtroResultado} onChange={(evento) => setFiltroResultado(evento.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-xs">
            <option value="todos">Todos os resultados</option>
            <option value="enviado">Enviados</option>
            <option value="falhou">Falhas</option>
            <option value="duplicado">Ignorados</option>
            <option value="interrompido">Interrompidos</option>
          </select>
          <select value={filtroTipo} onChange={(evento) => setFiltroTipo(evento.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-xs">
            <option value="todos">Todos os tipos</option>
            <option value="cliente">Cliente</option>
            <option value="responsavel">Responsavel</option>
            <option value="equipe">Equipe</option>
          </select>
          <select value={filtroPeriodo} onChange={(evento) => setFiltroPeriodo(evento.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-xs">
            <option value="todos">Todo período</option>
            <option value="1">Últimas 24h</option>
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
          </select>
        </div>
        {mensagensFiltradas.length === 0 ? (
          <p className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">
            {historicoMensagens.length === 0 ? 'Nenhuma mensagem foi registrada.' : 'Nenhum registro corresponde aos filtros.'}
          </p>
        ) : (
          <div className="max-h-80 overflow-auto rounded-xl border border-gray-200">
            <table className="w-full min-w-[900px] text-left text-xs">
              <thead className="sticky top-0 bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-3 py-2 font-medium">Data</th>
                  <th className="px-3 py-2 font-medium">Tipo</th>
                  <th className="px-3 py-2 font-medium">CNPJ</th>
                  <th className="px-3 py-2 font-medium">Arquivo</th>
                  <th className="px-3 py-2 font-medium">Prazo</th>
                  <th className="px-3 py-2 font-medium">Destino</th>
                  <th className="px-3 py-2 font-medium">Resultado</th>
                  <th className="px-3 py-2 font-medium">Motivo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mensagensFiltradas.map((mensagem) => (
                  <tr key={mensagem.id} className="hover:bg-gray-50/70">
                    <td className="whitespace-nowrap px-3 py-2 text-gray-600">{formatarDataHora(mensagem.enviado_em)}</td>
                    <td className="px-3 py-2 font-medium capitalize text-gray-800">{mensagem.tipo}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-700">{mensagem.cnpj || '--'}</td>
                    <td className="max-w-52 truncate px-3 py-2 text-gray-600" title={mensagem.arquivo}>{mensagem.arquivo || '--'}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-600">{mensagem.dias} dias</td>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-600">{mensagem.destinatario}</td>
                    <td className={`px-3 py-2 font-medium ${
                      mensagem.status === 'enviado'
                        ? 'text-green-600'
                        : mensagem.status === 'falhou'
                          ? 'text-red-600'
                          : mensagem.status === 'duplicado'
                            ? 'text-yellow-600'
                            : 'text-orange-600'
                    }`} title={mensagem.motivo}>
                      {mensagem.status === 'enviado'
                        ? 'Enviado'
                        : mensagem.status === 'falhou'
                          ? 'Falhou'
                          : mensagem.status === 'duplicado'
                            ? 'Ignorado'
                            : 'Interrompido'}
                    </td>
                    <td className="max-w-64 truncate px-3 py-2 text-gray-600" title={mensagem.motivo}>
                      {mensagem.motivo || '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h4 className="font-semibold text-gray-900">Execuções recentes</h4>
          <span className="text-xs text-gray-500">Últimas {Math.min(historico.length, 5)}</span>
        </div>
        {historico.length === 0 ? (
          <p className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">Nenhuma execução concluída registrada.</p>
        ) : (
          <div className="space-y-2">
            {historico.slice(0, 5).map((execucao) => {
              const expandida = execucaoExpandida === execucao.id;
              const envios = execucao.resumo_envios || resumoVazio;
              return (
                <article key={execucao.id} className="overflow-hidden rounded-xl border border-gray-200 text-xs">
                  <button type="button" onClick={() => setExecucaoExpandida(expandida ? null : execucao.id)} className="grid w-full grid-cols-2 gap-2 p-3 text-left hover:bg-gray-50 sm:grid-cols-[1fr_1.4fr_1fr_1.2fr_auto]">
                    <div><p className="text-gray-500">Resultado</p><p className={`mt-1 font-medium ${execucao.estado === 'concluida' ? 'text-green-600' : 'text-red-600'}`}>{execucao.estado === 'concluida' ? 'Concluída' : 'Falhou'}</p></div>
                    <div><p className="text-gray-500">Início</p><p className="mt-1 font-medium text-gray-800">{formatarDataHora(execucao.inicio)}</p></div>
                    <div><p className="text-gray-500">Duração</p><p className="mt-1 font-medium text-gray-800">{formatarDuracao(execucao.duracao_segundos)}</p></div>
                    <div><p className="text-gray-500">Avisos</p><p className="mt-1 font-medium text-gray-800">{execucao.notificacoes_teste ? `Teste: ${execucao.escopo_notificacoes_teste || 'completo'}` : 'Desativados'}</p></div>
                    <ChevronDown className={`mt-2 hidden h-4 w-4 text-gray-400 transition-transform sm:block ${expandida ? 'rotate-180' : ''}`} />
                  </button>
                  {expandida && (
                    <div className="grid grid-cols-2 gap-3 border-t border-gray-200 bg-gray-50 p-3 sm:grid-cols-4">
                      <div><p className="text-gray-500">Enviados</p><p className="mt-1 font-semibold text-green-600">{envios.whatscontabil_enviados}</p></div>
                      <div><p className="text-gray-500">Ignorados</p><p className="mt-1 font-semibold text-yellow-600">{envios.whatscontabil_duplicados}</p></div>
                      <div><p className="text-gray-500">Falhas</p><p className="mt-1 font-semibold text-red-600">{envios.whatscontabil_falhas}</p></div>
                      <div><p className="text-gray-500">Excel</p><p className="mt-1 font-semibold text-gray-800">{execucao.atualizou_excel ? 'Atualizado' : 'Não solicitado'}</p></div>
                      {execucao.erro && <p className="col-span-full rounded-lg bg-red-50 p-2 text-red-700">{execucao.erro}</p>}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
