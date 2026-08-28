'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle, ChevronDown, CircleDot, RefreshCw, Settings, XCircle } from 'lucide-react';

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';

type EstadoIntegracao = 'ok' | 'configurado' | 'atencao' | 'erro';

interface IntegracaoSaude {
  id: string;
  nome: string;
  estado: EstadoIntegracao;
  detalhe: string;
}

interface RespostaSaude {
  verificado_em: string;
  integracoes: IntegracaoSaude[];
}

interface IntegrationHealthPanelProps {
  chaveAdmin?: string;
  onOpenConfig?: () => void;
  embutido?: boolean;
}

const visualEstado: Record<EstadoIntegracao, { label: string; classe: string }> = {
  ok: { label: 'Operacional', classe: 'border-green-200 bg-green-50 text-green-800' },
  configurado: { label: 'Configurado', classe: 'border-blue-200 bg-blue-50 text-blue-800' },
  atencao: { label: 'Atenção', classe: 'border-amber-200 bg-amber-50 text-amber-800' },
  erro: { label: 'Indisponível', classe: 'border-red-200 bg-red-50 text-red-800' },
};

export default function IntegrationHealthPanel({ chaveAdmin, onOpenConfig, embutido = false }: IntegrationHealthPanelProps) {
  const [saude, setSaude] = useState<RespostaSaude | null>(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(false);
  const [expandido, setExpandido] = useState(true);

  const carregarSaude = useCallback(async () => {
    const chaveConsulta = chaveAdmin?.trim() || window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO) || '';
    if (!chaveConsulta) {
      setErro('Informe a chave administrativa para consultar as integrações.');
      return;
    }

    setCarregando(true);
    try {
      const resposta = await fetch('/api/automacao/saude', {
        headers: { 'X-Admin-Key': chaveConsulta },
        cache: 'no-store',
      });
      if (!resposta.ok) throw new Error('Não foi possível verificar as integrações.');
      setSaude(await resposta.json());
      setErro('');
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Falha ao verificar integrações.');
    } finally {
      setCarregando(false);
    }
  }, [chaveAdmin]);

  useEffect(() => {
    carregarSaude();
    const intervalo = window.setInterval(carregarSaude, 60000);
    const atualizarAoConfigurar = () => carregarSaude();
    window.addEventListener('certificados-monitor:automacao-alterada', atualizarAoConfigurar);
    return () => {
      window.clearInterval(intervalo);
      window.removeEventListener('certificados-monitor:automacao-alterada', atualizarAoConfigurar);
    };
  }, [carregarSaude]);

  const quantidadeProblemas = saude?.integracoes.filter((item) => item.estado === 'erro' || item.estado === 'atencao').length || 0;

  return (
    <section className={`${embutido ? '' : 'surface-enter mb-6'} overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm`}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={() => setExpandido((valor) => !valor)}
          className="flex min-w-0 items-center gap-3 text-left"
          aria-expanded={expandido}
        >
          <span className={`rounded-lg p-2 ${quantidadeProblemas ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
            {quantidadeProblemas ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle className="h-5 w-5" />}
          </span>
          <span className="min-w-0">
            <span className="block font-semibold text-gray-900">Saúde das integrações</span>
            <span className="mt-0.5 block text-xs text-gray-500">
              {erro || (saude ? `${quantidadeProblemas} item(ns) precisam de atenção` : 'Verificação passiva e segura')}
            </span>
          </span>
          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${expandido ? 'rotate-180' : ''}`} />
        </button>

        <div className="flex items-center gap-2">
          {saude && (
            <span className="hidden text-xs text-gray-500 sm:inline">
              {new Date(saude.verificado_em).toLocaleTimeString('pt-BR')}
            </span>
          )}
          <button
            type="button"
            onClick={carregarSaude}
            disabled={carregando}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-800 disabled:opacity-50"
            aria-label="Verificar integrações agora"
          >
            <RefreshCw className={`h-4 w-4 ${carregando ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {expandido && (
        <div className="border-t border-gray-200 p-5 sm:p-6">
          {erro && !saude ? (
            <div className="flex flex-col items-start justify-between gap-3 rounded-lg bg-amber-50 p-4 text-sm text-amber-800 sm:flex-row sm:items-center">
              <span>{erro}</span>
              <button
                type="button"
                onClick={onOpenConfig}
                className={`${onOpenConfig ? 'flex' : 'hidden'} shrink-0 items-center rounded-lg bg-white px-3 py-2 font-medium hover:bg-amber-100`}
              >
                <Settings className="mr-2 h-4 w-4" />
                Abrir configurações
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(saude?.integracoes || []).map((integracao) => {
                const visual = visualEstado[integracao.estado];
                const Icone = integracao.estado === 'ok'
                  ? CheckCircle
                  : integracao.estado === 'erro'
                    ? XCircle
                    : integracao.estado === 'atencao'
                      ? AlertTriangle
                      : CircleDot;
                return (
                  <article key={integracao.id} className="rounded-xl border border-gray-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-semibold text-gray-900">{integracao.nome}</h3>
                      <span className={`flex shrink-0 items-center rounded-full border px-2 py-1 text-[11px] font-medium ${visual.classe}`}>
                        <Icone className="mr-1 h-3 w-3" />
                        {visual.label}
                      </span>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-gray-600">{integracao.detalhe}</p>
                  </article>
                );
              })}
            </div>
          )}
          <p className="mt-4 text-xs text-gray-500">
            A verificação automática não abre conexões externas nem envia mensagens.
          </p>
        </div>
      )}
    </section>
  );
}
