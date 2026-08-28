'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, CheckCircle, Settings, XCircle } from 'lucide-react';

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';
const EVENTO_AUTOMACAO_ALTERADA = 'certificados-monitor:automacao-alterada';

interface AutomacaoStatus {
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
  logs: string[];
}

interface AutomationStatusBannerProps {
  onComplete: () => void | Promise<void>;
  onOpen: () => void;
}

function formatarDuracao(total: number | null) {
  if (total === null) return '--';
  const minutos = Math.floor(total / 60);
  const segundos = total % 60;
  return minutos > 0 ? `${minutos}min ${segundos}s` : `${segundos}s`;
}

export default function AutomationStatusBanner({
  onComplete,
  onOpen,
}: AutomationStatusBannerProps) {
  const [status, setStatus] = useState<AutomacaoStatus | null>(null);
  const [chaveAdmin, setChaveAdmin] = useState('');
  const estavaExecutandoRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const carregarStatus = useCallback(async (chave: string) => {
    if (!chave) return;
    try {
      const resposta = await fetch('/api/automacao/status', {
        headers: { 'X-Admin-Key': chave },
        cache: 'no-store',
      });
      if (!resposta.ok) return;

      const novoStatus: AutomacaoStatus = await resposta.json();
      const concluiuAgora =
        estavaExecutandoRef.current &&
        !novoStatus.executando &&
        novoStatus.codigo_saida !== null;

      estavaExecutandoRef.current = novoStatus.executando;
      setStatus(novoStatus);
      if (concluiuAgora) await onCompleteRef.current();
    } catch {
      // Mantem o ultimo estado conhecido durante reinicios curtos do backend.
    }
  }, []);

  useEffect(() => {
    const sincronizar = () => {
      const chave = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO) || '';
      setChaveAdmin(chave);
      carregarStatus(chave);
    };

    sincronizar();
    window.addEventListener(EVENTO_AUTOMACAO_ALTERADA, sincronizar);
    return () => window.removeEventListener(EVENTO_AUTOMACAO_ALTERADA, sincronizar);
  }, [carregarStatus]);

  useEffect(() => {
    if (!chaveAdmin) return;
    const intervalo = window.setInterval(
      () => carregarStatus(chaveAdmin),
      status?.executando ? 3000 : 30000,
    );
    return () => window.clearInterval(intervalo);
  }, [carregarStatus, chaveAdmin, status?.executando]);

  if (!chaveAdmin || !status || status.estado === 'aguardando') return null;

  const executando = status.executando;
  const sucesso = status.estado === 'concluida';
  const Icone = executando ? Activity : sucesso ? CheckCircle : XCircle;
  const cores = executando
    ? 'border-blue-200 bg-blue-50 text-blue-800'
    : sucesso
      ? 'border-green-200 bg-green-50 text-green-800'
      : 'border-red-200 bg-red-50 text-red-800';

  return (
    <div className={`mb-6 rounded-xl border p-4 shadow-sm ${cores}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Icone className={`mt-0.5 h-5 w-5 shrink-0 ${executando ? 'animate-pulse' : ''}`} />
          <div>
            <p className="font-medium">
              {executando
                ? 'Automacao em andamento'
                : sucesso
                  ? 'Ultima automacao concluida'
                  : 'Ultima automacao falhou'}
            </p>
            <p className="mt-1 text-sm opacity-80">
              Duracao: {formatarDuracao(status.duracao_segundos)}
              {status.atualizou_excel ? ' - Excel habilitado' : ''}
              {status.notificacoes_teste ? ' - Avisos em teste' : ''}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onOpen}
          className="flex items-center justify-center rounded-lg bg-white/70 px-3 py-2 text-sm font-medium hover:bg-white"
        >
          <Settings className="mr-2 h-4 w-4" />
          Ver detalhes
        </button>
      </div>
    </div>
  );
}
