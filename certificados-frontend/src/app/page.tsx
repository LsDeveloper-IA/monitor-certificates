'use client';

import { useState, useEffect } from 'react';
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
  Phone
  ,Moon
  ,Sun
  ,RefreshCw
} from 'lucide-react';
import CertificadoModal from '@/components/CertificadoModal';
import ConfigModal from '@/components/ConfigModal';
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
  const [filtro, setFiltro] = useState('todos');
  const [busca, setBusca] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState<'certificado' | 'config' | 'notificacao'>('certificado');
  const [modoEscuro, setModoEscuro] = useState(false);
  const [ultimaAtualizacao, setUltimaAtualizacao] = useState<Date | null>(null);
  const [paginaAtual, setPaginaAtual] = useState(0);
  const [itensPorPagina, setItensPorPagina] = useState(20);

  useEffect(() => {
    const escuroSalvo = localStorage.getItem('tema') === 'escuro';
    setModoEscuro(escuroSalvo);
    document.documentElement.classList.toggle('dark', escuroSalvo);
    carregarDados();
    const intervalo = window.setInterval(carregarDados, 30000);
    return () => window.clearInterval(intervalo);
  }, []);

  const alternarTema = () => {
    const novoTema = !modoEscuro;
    setModoEscuro(novoTema);
    document.documentElement.classList.toggle('dark', novoTema);
    localStorage.setItem('tema', novoTema ? 'escuro' : 'claro');
  };

  const carregarDados = async () => {
    try {
      setLoading(true);
      
      // Carregar certificados
      const respCertificados = await fetch('/api/certificados');
      const certificados = await respCertificados.json();
      setCertificados(certificados);
      
      // Carregar estatísticas
      const respEstatisticas = await fetch('/api/certificados/estatisticas');
      const stats = await respEstatisticas.json();
      setEstatisticas(stats);
      setUltimaAtualizacao(new Date());
      
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  const certificadosFiltrados = certificados.filter(cert => {
    const matchBusca = cert.nome_empresa.toLowerCase().includes(busca.toLowerCase()) ||
                      cert.cpf_cnpj.includes(busca) ||
                      (cert.responsavel?.toLowerCase().includes(busca.toLowerCase()) ?? false);
    
    if (!matchBusca) return false;
    
    switch (filtro) {
      case 'vencendo':
        return (cert.dias_para_vencimento ?? 0) <= 30 && (cert.dias_para_vencimento ?? 0) > 0;
      case 'urgente':
        return (cert.dias_para_vencimento ?? 0) <= 15 && (cert.dias_para_vencimento ?? 0) > 0;
      case 'vencidos':
        return (cert.dias_para_vencimento ?? 0) < 0;
      case 'pj':
        return cert.tipo === 'PJ';
      case 'pf':
        return cert.tipo === 'PF';
      default:
        return true;
    }
  });

  useEffect(() => {
    setPaginaAtual(0);
  }, [busca, filtro, itensPorPagina]);

  const totalPaginas = Math.ceil(certificadosFiltrados.length / itensPorPagina);
  const inicioPagina = paginaAtual * itensPorPagina;
  const certificadosDaPagina = certificadosFiltrados.slice(
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando dados...</p>
        </div>
      </div>
    );
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
              <div className="hidden sm:flex items-center text-xs text-gray-500">
                <RefreshCw className="w-4 h-4 mr-1" />
                {ultimaAtualizacao
                  ? `Atualizado ${ultimaAtualizacao.toLocaleTimeString('pt-BR')}`
                  : 'Atualizando...'}
              </div>
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
                onClick={() => { setModalType('notificacao'); setShowModal(true); }}
                className="p-2 text-gray-400 hover:text-gray-600 relative"
              >
                <Bell className="w-6 h-6" />
                {(estatisticas.vencendo_15_dias > 0) && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                    {estatisticas.vencendo_15_dias}
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
        {/* Cards de Estatísticas */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Shield className="w-6 h-6 text-blue-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Total</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.total}</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Vencendo (30d)</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencendo_30_dias}</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <div className="p-2 bg-red-100 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Urgente (15d)</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencendo_15_dias}</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <div className="p-2 bg-gray-100 rounded-lg">
                <XCircle className="w-6 h-6 text-gray-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Vencidos</p>
                <p className="text-2xl font-semibold text-gray-900">{estatisticas.vencidos}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Controles */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
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
                <option value="pj">Pessoa Jurídica</option>
                <option value="pf">Pessoa Física</option>
              </select>
            </div>

            <button
              onClick={() => { setModalType('certificado'); setShowModal(true); }}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
            >
              <Plus className="w-5 h-5 mr-2" />
              Novo Certificado
            </button>
          </div>
        </div>

        {/* Lista de Certificados */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
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
          
          <div className="w-full overflow-hidden">
            <table className="w-full table-fixed divide-y divide-gray-200">
              <colgroup>
                <col className="w-[25%]" />
                <col className="w-[13%]" />
                <col className="w-[21%]" />
                <col className="w-[13%]" />
                <col className="w-[10%]" />
                <col className="w-[18%]" />
              </colgroup>
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cliente
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Documento
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Arquivo
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Vencimento
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Contato
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {certificadosDaPagina.map((cert) => (
                  <tr key={cert.id} className="hover:bg-gray-50">
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
                              {cert.responsavel}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-4 align-top">
                      <div className="break-all text-sm text-gray-900">{cert.cpf_cnpj}</div>
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
              <p className="text-gray-500">Nenhum certificado encontrado</p>
            </div>
          )}
        </div>
      </div>

      {/* Modais */}
      <CertificadoModal
        isOpen={showModal && modalType === 'certificado'}
        onClose={() => setShowModal(false)}
        onSave={() => {
          // Recarregar dados após salvar
          carregarDados();
        }}
      />

      <ConfigModal
        isOpen={showModal && modalType === 'config'}
        onClose={() => setShowModal(false)}
      />

      {/* Modal de Notificações (placeholder) */}
      {showModal && modalType === 'notificacao' && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium mb-4 flex items-center">
              <Bell className="w-5 h-5 mr-2" />
              Central de Notificações
            </h3>
            <p className="text-gray-600 mb-4">
              Funcionalidade em desenvolvimento...
            </p>
            <button
              onClick={() => setShowModal(false)}
              className="bg-gray-200 text-gray-800 px-4 py-2 rounded-lg hover:bg-gray-300"
            >
              Fechar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

