'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { 
  Shield, 
  AlertTriangle, 
  Settings, 
  Plus,
  Search,
  Bell,
  CheckCircle,
  XCircle,
  Clock,
  Building,
  User,
  Mail,
  Phone,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  X,
  Moon,
  Sun,
  RefreshCw,
  FileWarning
} from 'lucide-react';
import CertificadoModal from '@/components/CertificadoModal';
import ConfigModal from '@/components/ConfigModal';
import AutomationStatusBanner from '@/components/AutomationStatusBanner';
import AutomationActivityPanel from '@/components/AutomationActivityPanel';
import ReactPaginate from 'react-paginate';

interface Certificado {
  id: number;
  nome_empresa: string;
  cpf_cnpj: string;
  tipo: 'PJ' | 'PF';
  data_vencimento: string;
  responsavel?: string;
  email_contato?: string;
  telefone_contato?: string;
  observacoes?: string;
  arquivo_drive_id?: string;
  ativo: boolean;
  dias_para_vencimento?: number;
}

interface Estatisticas {
  total: number;
  vencendo_30_dias: number;
  vencendo_15_dias: number;
  vencidos: number;
  pessoa_juridica: number;
  pessoa_fisica: number;
}

type TipoToast = 'success' | 'error' | 'info';
type TipoPendencia = 'urgente' | 'vencendo' | 'vencido' | 'sem_contato' | 'erro';
type FiltroPendencia = 'todas' | TipoPendencia;

interface ToastState {
  mensagem: string;
  tipo: TipoToast;
}

interface Pendencia {
  id: string;
  tipo: TipoPendencia;
  titulo: string;
  descricao: string;
  prioridade: number;
  certificado: Certificado;
}

type ColunaOrdenacao =
  | 'empresa'
  | 'documento'
  | 'arquivo'
  | 'vencimento'
  | 'status'
  | 'contato';
type DirecaoOrdenacao = 'asc' | 'desc';

const somenteDigitos = (valor: string) => valor.replace(/\D/g, '');

const formatarDocumento = (documento: string, tipo: 'PJ' | 'PF') => {
  const numeros = somenteDigitos(documento);

  if (tipo === 'PJ' && numeros.length === 14) {
    return numeros.replace(
      /^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,
      '$1.$2.$3/$4-$5'
    );
  }

  if (tipo === 'PF' && numeros.length === 11) {
    return numeros.replace(
      /^(\d{3})(\d{3})(\d{3})(\d{2})$/,
      '$1.$2.$3-$4'
    );
  }

  return documento;
};

const filtrosValidos = new Set([
  'todos',
  'vencendo',
  'urgente',
  'vencidos',
  'sem_contato',
  'erro',
  'pj',
  'pf',
]);
const CHAVE_PENDENCIAS_LIDAS = 'certificados-monitor:pendencias-lidas';

const possuiErroLeitura = (certificado: Certificado) => {
  const texto = certificado.observacoes?.toLocaleLowerCase('pt-BR') || '';
  return ['erro', 'senha', 'não encontrado', 'nao encontrado', 'inválido', 'invalido']
    .some((termo) => texto.includes(termo));
};

function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-gray-50" aria-label="Carregando certificados">
      <div className="h-16 border-b border-gray-200 bg-white" />
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 rounded-lg bg-white p-6 shadow">
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton mt-4 h-8 w-16 rounded" />
            </div>
          ))}
        </div>
        <div className="h-24 rounded-lg bg-white p-6 shadow">
          <div className="skeleton h-10 w-full rounded-lg" />
        </div>
        <div className="rounded-lg bg-white p-6 shadow">
          {[0, 1, 2, 3, 4].map((item) => (
            <div key={item} className="flex gap-6 border-b border-gray-200 py-5 last:border-0">
              <div className="skeleton h-4 w-1/3 rounded" />
              <div className="skeleton h-4 w-1/4 rounded" />
              <div className="skeleton h-4 flex-1 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [certificados, setCertificados] = useState<Certificado[]>([]);
  const [estatisticas, setEstatisticas] = useState<Estatisticas>({
    total: 0,
    vencendo_30_dias: 0,
    vencendo_15_dias: 0,
    vencidos: 0,
    pessoa_juridica: 0,
    pessoa_fisica: 0
  });
  const [loading, setLoading] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [filtro, setFiltro] = useState('todos');
  const [busca, setBusca] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState<'certificado' | 'config' | 'notificacao'>('certificado');
  const [modoEscuro, setModoEscuro] = useState(false);
  const [ultimaAtualizacao, setUltimaAtualizacao] = useState<Date | null>(null);
  const [paginaAtual, setPaginaAtual] = useState(0);
  const [itensPorPagina, setItensPorPagina] = useState(20);
  const [ordenacao, setOrdenacao] = useState<{
    coluna: ColunaOrdenacao | null;
    direcao: DirecaoOrdenacao;
  }>({ coluna: null, direcao: 'asc' });
  const [certificadoSelecionado, setCertificadoSelecionado] = useState<Certificado | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [filtroNotificacao, setFiltroNotificacao] = useState<FiltroPendencia>('todas');
  const [abaCentral, setAbaCentral] = useState<'pendencias' | 'atividade'>('pendencias');
  const [pendenciasLidas, setPendenciasLidas] = useState<Set<string>>(new Set());
  const [urlInicializada, setUrlInicializada] = useState(false);
  const toastTimerRef = useRef<number | null>(null);
  const ignorarPrimeiroResetRef = useRef(true);

  const mostrarToast = (mensagem: string, tipo: TipoToast = 'info') => {
    setToast({ mensagem, tipo });
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 4500);
  };

  useEffect(() => {
    const escuroSalvo = localStorage.getItem('tema') === 'escuro';
    setModoEscuro(escuroSalvo);
    document.documentElement.classList.toggle('dark', escuroSalvo);
    try {
      const idsLidos = JSON.parse(localStorage.getItem(CHAVE_PENDENCIAS_LIDAS) || '[]');
      if (Array.isArray(idsLidos)) setPendenciasLidas(new Set(idsLidos.map(String)));
    } catch {
      localStorage.removeItem(CHAVE_PENDENCIAS_LIDAS);
    }

    const parametros = new URLSearchParams(window.location.search);
    const filtroUrl = parametros.get('filtro');
    const colunaUrl = parametros.get('ordem') as ColunaOrdenacao | null;
    const direcaoUrl = parametros.get('direcao') as DirecaoOrdenacao | null;
    const paginaUrl = Number(parametros.get('pagina'));
    const itensUrl = Number(parametros.get('itens'));
    setBusca(parametros.get('busca') || '');
    if (filtroUrl && filtrosValidos.has(filtroUrl)) setFiltro(filtroUrl);
    if (colunaUrl && ['empresa', 'documento', 'arquivo', 'vencimento', 'status', 'contato'].includes(colunaUrl)) {
      setOrdenacao({ coluna: colunaUrl, direcao: direcaoUrl === 'desc' ? 'desc' : 'asc' });
    }
    if (paginaUrl > 0) setPaginaAtual(paginaUrl - 1);
    if ([10, 20, 50].includes(itensUrl)) setItensPorPagina(itensUrl);
    setUrlInicializada(true);
    carregarDados();

    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!urlInicializada) return;
    const parametros = new URLSearchParams();
    if (busca) parametros.set('busca', busca);
    if (filtro !== 'todos') parametros.set('filtro', filtro);
    if (paginaAtual > 0) parametros.set('pagina', String(paginaAtual + 1));
    if (itensPorPagina !== 20) parametros.set('itens', String(itensPorPagina));
    if (ordenacao.coluna) {
      parametros.set('ordem', ordenacao.coluna);
      parametros.set('direcao', ordenacao.direcao);
    }
    const consulta = parametros.toString();
    window.history.replaceState(null, '', consulta ? `?${consulta}` : window.location.pathname);
  }, [busca, filtro, paginaAtual, itensPorPagina, ordenacao, urlInicializada]);

  useEffect(() => {
    if (!showModal) return;
    const fecharComEscape = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') setShowModal(false);
    };
    window.addEventListener('keydown', fecharComEscape);
    return () => window.removeEventListener('keydown', fecharComEscape);
  }, [showModal]);

  const alternarTema = () => {
    const novoTema = !modoEscuro;
    setModoEscuro(novoTema);
    document.documentElement.classList.toggle('dark', novoTema);
    localStorage.setItem('tema', novoTema ? 'escuro' : 'claro');
  };

  const carregarDados = async (exibirTelaCarregamento = true) => {
    try {
      if (exibirTelaCarregamento) setLoading(true);
      setAtualizando(true);
      
      // Carregar certificados
      const respCertificados = await fetch('/api/certificados');
      if (!respCertificados.ok) throw new Error('Não foi possível carregar os certificados.');
      const dadosCertificados = await respCertificados.json();
      if (!Array.isArray(dadosCertificados)) throw new Error('Resposta inválida ao carregar certificados.');
      setCertificados(dadosCertificados);
      
      // Carregar estatísticas
      const respEstatisticas = await fetch('/api/certificados/estatisticas');
      if (!respEstatisticas.ok) throw new Error('Não foi possível carregar as estatísticas.');
      const stats = await respEstatisticas.json();
      setEstatisticas(stats);
      setUltimaAtualizacao(new Date());
      
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
      mostrarToast(error instanceof Error ? error.message : 'Erro ao carregar os dados.', 'error');
    } finally {
      setLoading(false);
      setAtualizando(false);
    }
  };

  const certificadosFiltrados = certificados.filter(cert => {
    const buscaDocumento = somenteDigitos(busca);
    const matchBusca = cert.nome_empresa.toLowerCase().includes(busca.toLowerCase()) ||
                      (buscaDocumento.length > 0 &&
                        somenteDigitos(cert.cpf_cnpj).includes(buscaDocumento)) ||
                      (cert.responsavel?.toLowerCase().includes(busca.toLowerCase()) ?? false);
    
    if (!matchBusca) return false;
    
    switch (filtro) {
      case 'vencendo':
        return cert.dias_para_vencimento !== undefined && cert.dias_para_vencimento <= 30 && cert.dias_para_vencimento >= 0;
      case 'urgente':
        return cert.dias_para_vencimento !== undefined && cert.dias_para_vencimento <= 15 && cert.dias_para_vencimento >= 0;
      case 'vencidos':
        return (cert.dias_para_vencimento ?? 0) < 0;
      case 'sem_contato':
        return !cert.email_contato && !cert.telefone_contato;
      case 'erro':
        return possuiErroLeitura(cert);
      case 'pj':
        return cert.tipo === 'PJ';
      case 'pf':
        return cert.tipo === 'PF';
      default:
        return true;
    }
  });

  const valorOrdenacao = (cert: Certificado, coluna: ColunaOrdenacao) => {
    switch (coluna) {
      case 'empresa':
        return cert.nome_empresa;
      case 'documento':
        return somenteDigitos(cert.cpf_cnpj);
      case 'arquivo':
        return cert.arquivo_drive_id || '';
      case 'vencimento':
        return new Date(cert.data_vencimento).getTime();
      case 'status':
        return cert.dias_para_vencimento ?? Number.POSITIVE_INFINITY;
      case 'contato':
        return cert.email_contato || cert.telefone_contato || '';
    }
  };

  const certificadosOrdenados = [...certificadosFiltrados].sort((a, b) => {
    if (!ordenacao.coluna) return 0;
    const valorA = valorOrdenacao(a, ordenacao.coluna);
    const valorB = valorOrdenacao(b, ordenacao.coluna);
    const comparacao =
      typeof valorA === 'number' && typeof valorB === 'number'
        ? valorA - valorB
        : String(valorA).localeCompare(String(valorB), 'pt-BR', {
            numeric: true,
            sensitivity: 'base',
          });
    return ordenacao.direcao === 'asc' ? comparacao : -comparacao;
  });

  const alternarOrdenacao = (coluna: ColunaOrdenacao) => {
    setOrdenacao((atual) => ({
      coluna,
      direcao:
        atual.coluna === coluna && atual.direcao === 'asc' ? 'desc' : 'asc',
    }));
  };

  const iconeOrdenacao = (coluna: ColunaOrdenacao) => {
    if (ordenacao.coluna !== coluna) {
      return <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />;
    }
    return ordenacao.direcao === 'asc' ? (
      <ArrowUp className="h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5" />
    );
  };

  useEffect(() => {
    if (!urlInicializada) return;
    if (ignorarPrimeiroResetRef.current) {
      ignorarPrimeiroResetRef.current = false;
      return;
    }
    setPaginaAtual(0);
  }, [busca, filtro, itensPorPagina, ordenacao, urlInicializada]);

  const totalPaginas = Math.ceil(certificadosFiltrados.length / itensPorPagina);
  const inicioPagina = paginaAtual * itensPorPagina;
  const certificadosDaPagina = certificadosOrdenados.slice(
    inicioPagina,
    inicioPagina + itensPorPagina
  );

  const formatarData = (data: string) => {
    return new Date(data).toLocaleDateString('pt-BR');
  };

  const getStatusColor = (dias?: number) => {
    if (!dias) return 'text-gray-500';
    if (dias < 0) return 'text-red-600';
    if (dias <= 15) return 'text-red-500';
    if (dias <= 30) return 'text-yellow-500';
    return 'text-green-500';
  };

  const getStatusIcon = (dias?: number) => {
    if (!dias) return <Clock className="w-4 h-4" />;
    if (dias < 0) return <XCircle className="w-4 h-4" />;
    if (dias <= 15) return <AlertTriangle className="w-4 h-4" />;
    if (dias <= 30) return <Clock className="w-4 h-4" />;
    return <CheckCircle className="w-4 h-4" />;
  };

  const filtrosRapidos = [
    { id: 'todos', label: 'Todos', quantidade: certificados.length },
    {
      id: 'vencendo',
      label: 'Até 30 dias',
      quantidade: certificados.filter((cert) => cert.dias_para_vencimento !== undefined && cert.dias_para_vencimento >= 0 && cert.dias_para_vencimento <= 30).length,
    },
    {
      id: 'urgente',
      label: 'Até 15 dias',
      quantidade: certificados.filter((cert) => cert.dias_para_vencimento !== undefined && cert.dias_para_vencimento >= 0 && cert.dias_para_vencimento <= 15).length,
    },
    {
      id: 'vencidos',
      label: 'Vencidos',
      quantidade: certificados.filter((cert) => (cert.dias_para_vencimento ?? 0) < 0).length,
    },
    {
      id: 'sem_contato',
      label: 'Sem contato',
      quantidade: certificados.filter((cert) => !cert.email_contato && !cert.telefone_contato).length,
    },
    {
      id: 'erro',
      label: 'Erro de leitura',
      quantidade: certificados.filter(possuiErroLeitura).length,
    },
  ];

  const pendencias: Pendencia[] = certificados
    .flatMap((certificado) => {
      const itens: Pendencia[] = [];
      const dias = certificado.dias_para_vencimento;

      if (dias !== undefined) {
        if (dias < 0) {
          itens.push({
            id: `${certificado.id}-vencido`,
            tipo: 'vencido',
            titulo: 'Certificado vencido',
            descricao: `Venceu há ${Math.abs(dias)} dias`,
            prioridade: 0,
            certificado,
          });
        } else if (dias <= 15) {
          itens.push({
            id: `${certificado.id}-urgente`,
            tipo: 'urgente',
            titulo: 'Renovação urgente',
            descricao: dias === 0 ? 'Vence hoje' : `Vence em ${dias} dias`,
            prioridade: 1,
            certificado,
          });
        } else if (dias <= 30) {
          itens.push({
            id: `${certificado.id}-vencendo`,
            tipo: 'vencendo',
            titulo: 'Vencimento próximo',
            descricao: `Vence em ${dias} dias`,
            prioridade: 2,
            certificado,
          });
        }
      }

      if (!certificado.email_contato && !certificado.telefone_contato) {
        itens.push({
          id: `${certificado.id}-sem-contato`,
          tipo: 'sem_contato',
          titulo: 'Contato não localizado',
          descricao: 'Empresa sem telefone e e-mail cadastrados',
          prioridade: 3,
          certificado,
        });
      }

      if (possuiErroLeitura(certificado)) {
        itens.push({
          id: `${certificado.id}-erro`,
          tipo: 'erro',
          titulo: 'Erro de leitura',
          descricao: certificado.observacoes || 'Verifique o certificado e a senha',
          prioridade: 4,
          certificado,
        });
      }

      return itens;
    })
    .sort((a, b) => a.prioridade - b.prioridade || a.certificado.nome_empresa.localeCompare(b.certificado.nome_empresa, 'pt-BR'));

  const pendenciasExibidas = filtroNotificacao === 'todas'
    ? pendencias
    : pendencias.filter((item) => item.tipo === filtroNotificacao);
  const pendenciasNaoLidas = pendencias.filter((item) => !pendenciasLidas.has(item.id));

  useEffect(() => {
    if (loading) return;
    const idsAtuais = new Set(pendencias.map((item) => item.id));
    setPendenciasLidas((idsAnteriores) => {
      const idsValidos = new Set([...idsAnteriores].filter((id) => idsAtuais.has(id)));
      if (idsValidos.size === idsAnteriores.size) return idsAnteriores;
      localStorage.setItem(CHAVE_PENDENCIAS_LIDAS, JSON.stringify([...idsValidos]));
      return idsValidos;
    });
  }, [certificados, loading]);

  const resumoPendencias: Array<{ id: FiltroPendencia; label: string; quantidade: number }> = [
    { id: 'todas', label: 'Todas', quantidade: pendencias.length },
    { id: 'urgente', label: 'Urgentes', quantidade: pendencias.filter((item) => item.tipo === 'urgente').length },
    { id: 'vencendo', label: 'Até 30 dias', quantidade: pendencias.filter((item) => item.tipo === 'vencendo').length },
    { id: 'vencido', label: 'Vencidos', quantidade: pendencias.filter((item) => item.tipo === 'vencido').length },
    { id: 'sem_contato', label: 'Sem contato', quantidade: pendencias.filter((item) => item.tipo === 'sem_contato').length },
    { id: 'erro', label: 'Erros', quantidade: pendencias.filter((item) => item.tipo === 'erro').length },
  ];

  const estiloPendencia = (tipo: TipoPendencia) => {
    switch (tipo) {
      case 'vencido':
      case 'urgente':
        return 'border-red-200 bg-red-50 text-red-700';
      case 'vencendo':
        return 'border-yellow-200 bg-yellow-50 text-yellow-700';
      case 'sem_contato':
        return 'border-blue-200 bg-blue-50 text-blue-700';
      case 'erro':
        return 'border-orange-200 bg-orange-50 text-orange-700';
    }
  };

  const aplicarPendenciasNaTabela = () => {
    const mapa: Record<FiltroPendencia, string> = {
      todas: 'todos',
      urgente: 'urgente',
      vencendo: 'vencendo',
      vencido: 'vencidos',
      sem_contato: 'sem_contato',
      erro: 'erro',
    };
    setFiltro(mapa[filtroNotificacao]);
    setShowModal(false);
  };

  const salvarPendenciasLidas = (novosIds: Set<string>) => {
    setPendenciasLidas(novosIds);
    localStorage.setItem(CHAVE_PENDENCIAS_LIDAS, JSON.stringify([...novosIds]));
  };

  const marcarPendenciaComoLida = (id: string) => {
    if (pendenciasLidas.has(id)) return;
    const novosIds = new Set(pendenciasLidas);
    novosIds.add(id);
    salvarPendenciasLidas(novosIds);
  };

  const marcarTodasPendenciasComoLidas = () => {
    const novosIds = new Set(pendenciasLidas);
    pendencias.forEach((item) => novosIds.add(item.id));
    salvarPendenciasLidas(novosIds);
  };

  const limparFiltros = () => {
    setBusca('');
    setFiltro('todos');
    setOrdenacao({ coluna: null, direcao: 'asc' });
  };

  const abrirCertificado = (certificado: Certificado) => {
    setCertificadoSelecionado(certificado);
    setModalType('certificado');
    setShowModal(true);
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Shield className="w-8 h-8 text-blue-600 mr-3" />
              <h1 className="text-xl font-semibold text-gray-900">
                Monitor de Certificados Digitais
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <Link
                href="/certificados-vencidos"
                className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
                title="Certificados vencidos"
              >
                <FileWarning className="h-4 w-4" />
                <span className="hidden md:inline">Certificados vencidos</span>
              </Link>
              <button
                type="button"
                onClick={() => carregarDados(false)}
                disabled={atualizando}
                className="hidden sm:flex items-center rounded-lg px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
                title="Atualizar dados manualmente"
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${atualizando ? 'animate-spin' : ''}`} />
                {atualizando
                  ? 'Atualizando...'
                  : ultimaAtualizacao
                    ? `Atualizado ${ultimaAtualizacao.toLocaleTimeString('pt-BR')}`
                    : 'Atualizar dados'}
              </button>
              <button
                onClick={alternarTema}
                className="p-2 text-gray-400 hover:text-gray-600"
                title={modoEscuro ? 'Usar modo claro' : 'Usar modo escuro'}
                aria-label={modoEscuro ? 'Usar modo claro' : 'Usar modo escuro'}
              >
                {modoEscuro
                  ? <Sun className="w-6 h-6" />
                  : <Moon className="w-6 h-6" />}
              </button>
              <button 
                onClick={() => { setAbaCentral('pendencias'); setFiltroNotificacao('todas'); setModalType('notificacao'); setShowModal(true); }}
                className="p-2 text-gray-400 hover:text-gray-600 relative"
                title="Abrir central de pendências"
                aria-label={`Abrir central de pendências: ${pendenciasNaoLidas.length} não lidas`}
              >
                <Bell className="w-6 h-6" />
                {pendenciasNaoLidas.length > 0 && (
                  <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                    {pendenciasNaoLidas.length > 99 ? '99+' : pendenciasNaoLidas.length}
                  </span>
                )}
              </button>
              <button 
                onClick={() => { setModalType('config'); setShowModal(true); }}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <Settings className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <AutomationStatusBanner
          onComplete={() => {
            mostrarToast('Automação concluída. Os dados foram atualizados.', 'success');
            return carregarDados(false);
          }}
          onOpen={() => { setModalType('config'); setShowModal(true); }}
        />

        {/* Cards de Estatísticas */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <button
            type="button"
            onClick={() => setFiltro('todos')}
            aria-pressed={filtro === 'todos'}
            className={`dashboard-card surface-enter w-full rounded-lg bg-white p-6 text-left shadow ${filtro === 'todos' ? 'ring-2 ring-blue-500' : ''}`}
          >
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Shield className="w-6 h-6 text-blue-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Total</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.total}</p>
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setFiltro('vencendo')}
            aria-pressed={filtro === 'vencendo'}
            className={`dashboard-card surface-enter w-full rounded-lg bg-white p-6 text-left shadow ${filtro === 'vencendo' ? 'ring-2 ring-yellow-500' : ''}`}
          >
            <div className="flex items-center">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Vencendo (30d)</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencendo_30_dias}</p>
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setFiltro('urgente')}
            aria-pressed={filtro === 'urgente'}
            className={`dashboard-card surface-enter w-full rounded-lg bg-white p-6 text-left shadow ${filtro === 'urgente' ? 'ring-2 ring-red-500' : ''}`}
          >
            <div className="flex items-center">
              <div className="p-2 bg-red-100 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Urgente (15d)</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencendo_15_dias}</p>
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setFiltro('vencidos')}
            aria-pressed={filtro === 'vencidos'}
            className={`dashboard-card surface-enter w-full rounded-lg bg-white p-6 text-left shadow ${filtro === 'vencidos' ? 'ring-2 ring-gray-500' : ''}`}
          >
            <div className="flex items-center">
              <div className="p-2 bg-gray-100 rounded-lg">
                <XCircle className="w-6 h-6 text-gray-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Vencidos</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencidos}</p>
              </div>
            </div>
          </button>
        </div>

        {/* Controles */}
        <div className="surface-enter bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
            <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
              <div className="relative">
                <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar certificados..."
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              
              <select
                value={filtro}
                onChange={(e) => setFiltro(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="todos">Todos</option>
                <option value="vencendo">Vencendo (30d)</option>
                <option value="urgente">Urgente (15d)</option>
                <option value="vencidos">Vencidos</option>
                <option value="sem_contato">Sem contato</option>
                <option value="erro">Erro de leitura</option>
                <option value="pj">Pessoa Jurídica</option>
                <option value="pf">Pessoa Física</option>
              </select>
            </div>

            <button
              onClick={() => { setCertificadoSelecionado(null); setModalType('certificado'); setShowModal(true); }}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
            >
              <Plus className="w-5 h-5 mr-2" />
              Novo Certificado
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-2 border-t border-gray-200 pt-4" aria-label="Filtros rápidos">
            {filtrosRapidos.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setFiltro(item.id)}
                aria-pressed={filtro === item.id}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium ${
                  filtro === item.id
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : 'border-gray-300 bg-white text-gray-600 hover:border-blue-400 hover:text-blue-600'
                }`}
              >
                {item.label} <span className="ml-1 opacity-75">{item.quantidade}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Lista de Certificados */}
        <div className="surface-enter bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h3 className="text-lg font-medium text-gray-900">
                Certificados ({certificadosFiltrados.length})
              </h3>
              {certificadosFiltrados.length > 0 && (
                <p className="text-sm text-gray-500">
                  Exibindo {inicioPagina + 1}–{Math.min(inicioPagina + itensPorPagina, certificadosFiltrados.length)}
                </p>
              )}
            </div>
            <label className="text-sm text-gray-600 flex items-center gap-2">
              Itens por página
              <select
                value={itensPorPagina}
                onChange={(evento) => setItensPorPagina(Number(evento.target.value))}
                className="px-3 py-1.5 border border-gray-300 rounded-lg"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>
          </div>
          
          <div className="hidden max-h-[70vh] w-full overflow-y-auto md:block">
            <table className="w-full table-fixed divide-y divide-gray-200">
              <colgroup>
                <col className="w-[25%]" />
                <col className="w-[13%]" />
                <col className="w-[21%]" />
                <col className="w-[13%]" />
                <col className="w-[10%]" />
                <col className="w-[18%]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-gray-50 shadow-sm">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('empresa')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Cliente {iconeOrdenacao('empresa')}
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('documento')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Documento {iconeOrdenacao('documento')}
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('arquivo')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Arquivo {iconeOrdenacao('arquivo')}
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('vencimento')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Vencimento {iconeOrdenacao('vencimento')}
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('status')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Status {iconeOrdenacao('status')}
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button type="button" onClick={() => alternarOrdenacao('contato')} className="certificate-sort-button flex items-center gap-1.5 hover:text-gray-800">
                      Contato {iconeOrdenacao('contato')}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {certificadosDaPagina.map((cert) => (
                  <tr
                    key={cert.id}
                    className="certificate-row cursor-pointer hover:bg-gray-50"
                    tabIndex={0}
                    role="button"
                    aria-label={`Abrir detalhes de ${cert.nome_empresa}`}
                    onClick={() => abrirCertificado(cert)}
                    onKeyDown={(evento) => {
                      if (evento.key === 'Enter' || evento.key === ' ') {
                        evento.preventDefault();
                        abrirCertificado(cert);
                      }
                    }}
                  >
                    <td className="px-3 py-4 align-top">
                      <div className="flex min-w-0 items-start">
                        <div className="flex-shrink-0">
                          {cert.tipo === 'PJ' ? (
                            <Building className="w-6 h-6 text-gray-400" />
                          ) : (
                            <User className="w-6 h-6 text-gray-400" />
                          )}
                        </div>
                        <div className="ml-3 min-w-0">
                          <div className="break-words text-sm font-medium text-gray-900">
                            {cert.nome_empresa}
                          </div>
                          {cert.responsavel && (
                            <div className="mt-1 break-words text-xs text-gray-500">
                              {cert.responsavel.toLocaleUpperCase('pt-BR')}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-4 align-top">
                      <div className="text-sm text-gray-900">
                        {formatarDocumento(cert.cpf_cnpj, cert.tipo)}
                      </div>
                      <div className="mt-1 text-xs text-gray-500">{cert.tipo}</div>
                    </td>
                    <td className="px-3 py-4 align-top">
                      <div className="break-all text-sm text-gray-900">
                        {cert.arquivo_drive_id || 'Nao informado'}
                      </div>
                    </td>
                    <td className="px-3 py-4 align-top">
                      <div className="text-sm text-gray-900">
                        {formatarData(cert.data_vencimento)}
                      </div>
                      {cert.dias_para_vencimento !== undefined && (
                        <div className="mt-1 text-xs text-gray-500">
                          {cert.dias_para_vencimento < 0 
                            ? `${Math.abs(cert.dias_para_vencimento)} dias atrás`
                            : `${cert.dias_para_vencimento} dias restantes`
                          }
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-4 align-top">
                      <div className={`flex items-start ${getStatusColor(cert.dias_para_vencimento)}`}>
                        {getStatusIcon(cert.dias_para_vencimento)}
                        <span className="ml-2 text-sm">
                          {cert.dias_para_vencimento === undefined ? 'Carregando...' :
                           cert.dias_para_vencimento < 0 ? 'Vencido' :
                           cert.dias_para_vencimento <= 15 ? 'Urgente' :
                           cert.dias_para_vencimento <= 30 ? 'Vencendo' : 'OK'}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-4 align-top text-xs text-gray-500">
                      <div className="space-y-1">
                        {cert.email_contato && (
                          <div className="flex min-w-0 items-start">
                            <Mail className="mr-1.5 mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <span className="min-w-0 break-all">{cert.email_contato}</span>
                          </div>
                        )}
                        {cert.telefone_contato && (
                          <div className="flex min-w-0 items-start">
                            <Phone className="mr-1.5 mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <span className="min-w-0 break-all">{cert.telefone_contato}</span>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="divide-y divide-gray-200 md:hidden">
            {certificadosDaPagina.map((cert) => (
              <button
                key={cert.id}
                type="button"
                onClick={() => abrirCertificado(cert)}
                className="certificate-mobile-card block w-full p-4 text-left hover:bg-gray-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-gray-900">
                      {cert.nome_empresa}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {formatarDocumento(cert.cpf_cnpj, cert.tipo)} · {cert.tipo}
                    </p>
                  </div>
                  <div className={`flex shrink-0 items-center ${getStatusColor(cert.dias_para_vencimento)}`}>
                    {getStatusIcon(cert.dias_para_vencimento)}
                    <span className="ml-1 text-xs font-medium">
                      {cert.dias_para_vencimento === undefined ? 'Sem prazo' :
                       cert.dias_para_vencimento < 0 ? 'Vencido' :
                       cert.dias_para_vencimento <= 15 ? 'Urgente' :
                       cert.dias_para_vencimento <= 30 ? 'Vencendo' : 'OK'}
                    </span>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-gray-500">Vencimento</p>
                    <p className="mt-1 font-medium text-gray-800">{formatarData(cert.data_vencimento)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Prazo</p>
                    <p className="mt-1 font-medium text-gray-800">
                      {cert.dias_para_vencimento === undefined
                        ? 'Não informado'
                        : cert.dias_para_vencimento < 0
                          ? `${Math.abs(cert.dias_para_vencimento)} dias atrás`
                          : `${cert.dias_para_vencimento} dias restantes`}
                    </p>
                  </div>
                </div>

                {(cert.email_contato || cert.telefone_contato) && (
                  <div className="mt-4 space-y-1 border-t border-gray-200 pt-3 text-xs text-gray-500">
                    {cert.email_contato && (
                      <div className="flex items-start gap-1.5">
                        <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span className="break-all">{cert.email_contato}</span>
                      </div>
                    )}
                    {cert.telefone_contato && (
                      <div className="flex items-start gap-1.5">
                        <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>{cert.telefone_contato}</span>
                      </div>
                    )}
                  </div>
                )}
              </button>
            ))}
          </div>

          {totalPaginas > 1 && (
            <div className="px-6 py-4 border-t border-gray-200 flex justify-center">
              <ReactPaginate
                previousLabel="Anterior"
                nextLabel="Próxima"
                breakLabel="..."
                pageCount={totalPaginas}
                forcePage={Math.min(paginaAtual, totalPaginas - 1)}
                onPageChange={({ selected }) => setPaginaAtual(selected)}
                marginPagesDisplayed={1}
                pageRangeDisplayed={3}
                containerClassName="flex flex-wrap items-center justify-center gap-2 text-sm"
                pageLinkClassName="block px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
                previousLinkClassName="block px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
                nextLinkClassName="block px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
                activeLinkClassName="bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                disabledClassName="opacity-40 pointer-events-none"
              />
            </div>
          )}

          {certificadosFiltrados.length === 0 && (
            <div className="text-center py-12">
              <Shield className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="font-medium text-gray-700">Nenhum certificado encontrado</p>
              <p className="mt-1 text-sm text-gray-500">
                Tente remover a busca ou selecionar outro filtro.
              </p>
              <button
                type="button"
                onClick={limparFiltros}
                className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Limpar filtros
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Modais */}
      <CertificadoModal
        isOpen={showModal && modalType === 'certificado'}
        certificado={certificadoSelecionado || undefined}
        somenteLeitura={Boolean(certificadoSelecionado)}
        onClose={() => { setShowModal(false); setCertificadoSelecionado(null); }}
        onSave={() => {
          // Recarregar dados após salvar
          carregarDados(false);
          mostrarToast(
            certificadoSelecionado ? 'Certificado atualizado com sucesso.' : 'Certificado criado com sucesso.',
            'success',
          );
        }}
      />

      <ConfigModal
        isOpen={showModal && modalType === 'config'}
        onClose={() => setShowModal(false)}
      />

      {/* Modal de Notificações (placeholder) */}
      {showModal && modalType === 'notificacao' && (
        <div
          className="modal-backdrop fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
          onMouseDown={(evento) => {
            if (evento.target === evento.currentTarget) setShowModal(false);
          }}
        >
          <div
            className="modal-panel flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-central-pendencias"
          >
            <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-5 py-4 sm:px-6">
              <div>
                <h3 id="titulo-central-pendencias" className="flex items-center text-lg font-semibold text-gray-900">
                  <Bell className="mr-2 h-5 w-5 text-blue-600" />
                  Central de pendências
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  {pendencias.length} aviso{pendencias.length === 1 ? '' : 's'} · {pendenciasNaoLidas.length} não lido{pendenciasNaoLidas.length === 1 ? '' : 's'}.
                </p>
                {ultimaAtualizacao && (
                  <p className="mt-1 text-xs text-gray-400">
                    Dados atualizados às {ultimaAtualizacao.toLocaleTimeString('pt-BR')}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {abaCentral === 'pendencias' && pendenciasNaoLidas.length > 0 && (
                  <button
                    type="button"
                    onClick={marcarTodasPendenciasComoLidas}
                    className="flex items-center rounded-lg px-2 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 sm:px-3"
                    aria-label="Marcar todas as pendências como lidas"
                  >
                    <CheckCircle className="h-4 w-4 sm:mr-1.5" />
                    <span className="hidden sm:inline">Marcar todas como lidas</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                  aria-label="Fechar central de pendências"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex border-b border-gray-200 px-5 sm:px-6" role="tablist" aria-label="Seções da central">
              <button
                type="button"
                role="tab"
                aria-selected={abaCentral === 'pendencias'}
                onClick={() => setAbaCentral('pendencias')}
                className={`border-b-2 px-4 py-3 text-sm font-medium ${
                  abaCentral === 'pendencias'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                Pendências
                {pendenciasNaoLidas.length > 0 && (
                  <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">{pendenciasNaoLidas.length}</span>
                )}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={abaCentral === 'atividade'}
                onClick={() => setAbaCentral('atividade')}
                className={`border-b-2 px-4 py-3 text-sm font-medium ${
                  abaCentral === 'atividade'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                Atividade da automação
              </button>
            </div>

            <div className={`${abaCentral === 'pendencias' ? 'flex' : 'hidden'} flex-wrap gap-2 border-b border-gray-200 px-5 py-3 sm:px-6`} aria-label="Categorias de pendências">
              {resumoPendencias.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setFiltroNotificacao(item.id)}
                  aria-pressed={filtroNotificacao === item.id}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                    filtroNotificacao === item.id
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-gray-300 bg-white text-gray-600 hover:border-blue-400 hover:text-blue-600'
                  }`}
                >
                  {item.label} <span className="ml-1 opacity-75">{item.quantidade}</span>
                </button>
              ))}
            </div>

            <div className={`${abaCentral === 'pendencias' ? 'block' : 'hidden'} min-h-0 flex-1 overflow-y-auto`}>
              {pendenciasExibidas.length === 0 ? (
                <div className="px-6 py-14 text-center">
                  <CheckCircle className="mx-auto h-11 w-11 text-green-500" />
                  <p className="mt-3 font-medium text-gray-800">Nenhuma pendência nesta categoria</p>
                  <p className="mt-1 text-sm text-gray-500">Os dados carregados não possuem avisos desse tipo.</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {pendenciasExibidas.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        marcarPendenciaComoLida(item.id);
                        abrirCertificado(item.certificado);
                      }}
                      className={`notification-item flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-gray-50 sm:px-6 ${
                        pendenciasLidas.has(item.id) ? 'opacity-75' : 'notification-unread'
                      }`}
                    >
                      <span className={`mt-0.5 rounded-lg border p-2 ${estiloPendencia(item.tipo)}`}>
                        {item.tipo === 'urgente' || item.tipo === 'vencido' || item.tipo === 'erro' ? (
                          <AlertTriangle className="h-4 w-4" />
                        ) : item.tipo === 'sem_contato' ? (
                          <Phone className="h-4 w-4" />
                        ) : (
                          <Clock className="h-4 w-4" />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <span className="break-words text-sm font-semibold text-gray-900">
                            {item.certificado.nome_empresa}
                          </span>
                          {!pendenciasLidas.has(item.id) && (
                            <span className="h-2 w-2 shrink-0 rounded-full bg-blue-600" aria-label="Não lida" />
                          )}
                          <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${estiloPendencia(item.tipo)}`}>
                            {item.titulo}
                          </span>
                        </span>
                        <span className="mt-1 block break-words text-sm text-gray-600">
                          {item.descricao}
                        </span>
                        <span className="mt-1 block text-xs text-gray-400">
                          {formatarDocumento(item.certificado.cpf_cnpj, item.certificado.tipo)} · clique para ver detalhes
                        </span>
                      </span>
                      <ArrowDown className="mt-2 h-4 w-4 -rotate-90 text-gray-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className={`${abaCentral === 'atividade' ? 'block' : 'hidden'} min-h-0 flex-1 overflow-y-auto`}>
              {abaCentral === 'atividade' && <AutomationActivityPanel />}
            </div>

            <div className={`${abaCentral === 'pendencias' ? 'flex' : 'hidden'} flex-col-reverse gap-2 border-t border-gray-200 bg-gray-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6`}>
              <p className="text-xs text-gray-500">Esta central apenas exibe dados; nenhuma mensagem é enviada.</p>
              <button
                type="button"
                onClick={aplicarPendenciasNaTabela}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Mostrar na tabela
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={`toast-enter fixed right-4 top-4 z-[70] flex max-w-sm items-start gap-3 rounded-xl border px-4 py-3 shadow-lg ${
            toast.tipo === 'success'
              ? 'border-green-200 bg-green-50 text-green-800'
              : toast.tipo === 'error'
                ? 'border-red-200 bg-red-50 text-red-800'
                : 'border-blue-200 bg-blue-50 text-blue-800'
          }`}
          role="status"
          aria-live="polite"
        >
          {toast.tipo === 'success' ? (
            <CheckCircle className="mt-0.5 h-5 w-5 shrink-0" />
          ) : toast.tipo === 'error' ? (
            <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
          ) : (
            <Bell className="mt-0.5 h-5 w-5 shrink-0" />
          )}
          <span className="text-sm font-medium">{toast.mensagem}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="ml-auto text-current opacity-60 hover:opacity-100"
            aria-label="Fechar aviso"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

