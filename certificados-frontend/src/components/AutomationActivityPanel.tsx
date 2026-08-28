'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle, Clock, Mail, MessageCircle, RefreshCw, XCircle } from 'lucide-react';

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';

interface ResumoEnvios {
  email_enviados: number;
  email_duplicados: number;
  email_falhas: number;
  whatscontabil_enviados: number;
  whatscontabil_duplicados: number;
  whatscontabil_falhas: number;
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
  resumo_envios?: ResumoEnvios;
  logs?: string[];
}

const resumoVazio: ResumoEnvios = {
  email_enviados: 0,
  email_duplicados: 0,
  email_falhas: 0,
  whatscontabil_enviados: 0,
  whatscontabil_duplicados: 0,
  whatscontabil_falhas: 0,
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
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState('');

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
      const [respostaStatus, respostaHistorico] = await Promise.all([
        fetch('/api/automacao/status', { headers: cabecalhos, cache: 'no-store' }),
        fetch('/api/automacao/historico', { headers: cabecalhos, cache: 'no-store' }),
      ]);

      if (!respostaStatus.ok || !respostaHistorico.ok) {
        throw new Error('Não foi possível consultar a atividade da automação.');
      }

      const novoStatus = await respostaStatus.json();
      const novoHistorico = await respostaHistorico.json();
      setStatus(novoStatus);
      setHistorico(novoHistorico.execucoes || []);
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
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-blue-100">
            <div className="h-full w-full animate-pulse rounded-full bg-blue-500" />
          </div>
        )}
        {status.erro && <p className="mt-3 text-sm">{status.erro}</p>}
      </section>

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
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div><p className="text-xl font-semibold text-green-600">{resumo.whatscontabil_enviados}</p><p className="text-gray-500">Enviados</p></div>
            <div><p className="text-xl font-semibold text-yellow-600">{resumo.whatscontabil_duplicados}</p><p className="text-gray-500">Ignorados</p></div>
            <div><p className="text-xl font-semibold text-red-600">{resumo.whatscontabil_falhas}</p><p className="text-gray-500">Falhas</p></div>
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
        <div className="mb-2 flex items-center justify-between gap-3">
          <h4 className="font-semibold text-gray-900">Execuções recentes</h4>
          <span className="text-xs text-gray-500">Últimas {Math.min(historico.length, 5)}</span>
        </div>
        {historico.length === 0 ? (
          <p className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">Nenhuma execução concluída registrada.</p>
        ) : (
          <div className="space-y-2">
            {historico.slice(0, 5).map((execucao) => (
              <div key={execucao.id} className="grid grid-cols-2 gap-2 rounded-xl border border-gray-200 p-3 text-xs sm:grid-cols-4">
                <div><p className="text-gray-500">Resultado</p><p className={`mt-1 font-medium ${execucao.estado === 'concluida' ? 'text-green-600' : 'text-red-600'}`}>{execucao.estado === 'concluida' ? 'Concluída' : 'Falhou'}</p></div>
                <div><p className="text-gray-500">Início</p><p className="mt-1 font-medium text-gray-800">{formatarDataHora(execucao.inicio)}</p></div>
                <div><p className="text-gray-500">Duração</p><p className="mt-1 font-medium text-gray-800">{formatarDuracao(execucao.duracao_segundos)}</p></div>
                <div><p className="text-gray-500">Avisos</p><p className="mt-1 font-medium text-gray-800">{execucao.notificacoes_teste ? 'Teste habilitado' : 'Desativados'}</p></div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
