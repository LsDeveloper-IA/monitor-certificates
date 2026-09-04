'use client';

import { useEffect, useRef, useState } from 'react';
import { Activity, X, Save, Mail, MessageCircle, TestTube, Play, Pause, Settings, HeartPulse } from 'lucide-react';
import IntegrationHealthPanel from '@/components/IntegrationHealthPanel';

interface ConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type EscopoMensagensTeste = 'nenhum' | 'relatorios' | 'clientes' | 'completo';

interface HistoricoExecucao {
  id: string;
  estado: 'concluida' | 'falhou';
  inicio: string;
  fim: string;
  duracao_segundos: number;
  codigo_saida: number;
  erro: string | null;
  atualizou_excel: boolean;
  notificacoes_teste: boolean;
  escopo_notificacoes_teste?: EscopoMensagensTeste;
  forcou_reenvio_teste?: boolean;
}

interface PreviaEnvio {
  certificadosAviso: number;
  avisosCliente: number;
  pendenciasEquipe: number;
  totalCertificados: number;
}

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';
const EVENTO_AUTOMACAO_ALTERADA = 'certificados-monitor:automacao-alterada';

function formatarDuracao(totalSegundos: number | null) {
  if (totalSegundos === null) return '--';
  const minutos = Math.floor(totalSegundos / 60);
  const segundos = totalSegundos % 60;
  return minutos > 0 ? `${minutos}min ${segundos}s` : `${segundos}s`;
}

function formatarDataHora(valor: string | null) {
  if (!valor) return '--';
  return new Date(valor).toLocaleString('pt-BR');
}

export default function ConfigModal({
  isOpen,
  onClose,
}: ConfigModalProps) {
  const [activeTab, setActiveTab] = useState('automacao');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');

  // Estados para configuração de e-mail
  const [emailConfig, setEmailConfig] = useState({
    smtp_server: 'smtp.gmail.com',
    smtp_port: 587,
    usuario: '',
    senha: ''
  });

  // Estados para configuração do WhatsApp
  const [whatsContabilStatus, setWhatsContabilStatus] = useState({
    url_configurada: false,
    token_configurado: false,
    modo: 'desativado',
    numero_teste: null as string | null,
    whatsapp_id: null as string | null,
    conectado: false,
    quantidade_conexoes: null as number | null,
    quantidade_templates: null as number | null,
    conexao: null as null | {
      id?: string | number;
      nome?: string;
      status?: string;
      oficial?: boolean;
    },
  });
  // Mantido temporariamente apenas para compatibilidade com o bloco legado,
  // que nao e mais exibido na interface.
  const [whatsappConfig, setWhatsappConfig] = useState({
    token: '',
    phone_id: '',
  });

  // Estados para destinatários
  const [destinatarios, setDestinatarios] = useState({
    emails: [''],
    telefones: ['']
  });

  // Estados para agendador
  const [agendadorStatus, setAgendadorStatus] = useState({
    ativo: false,
    monitorando: false,
    horarios: ['09:00', '14:00'] as string[],
    atualizar_excel: false,
    notificacoes_teste: false,
    proxima_execucao: null as string | null,
    ultima_execucao: null as string | null,
    ultimo_erro: null as string | null,
    execucoes_hoje: [] as string[],
    horarios_pendentes: [] as string[],
    horarios_atrasados: [] as string[],
    situacao: 'desativado' as 'normal' | 'desativado' | 'monitor_parado' | 'atrasado',
  });
  const [primeiroHorarioAgendador, setPrimeiroHorarioAgendador] = useState('09:00');
  const [segundoHorarioAgendador, setSegundoHorarioAgendador] = useState('14:00');
  const [excelAgendador, setExcelAgendador] = useState(false);
  const [notificacoesTesteAgendador, setNotificacoesTesteAgendador] = useState(false);
  const [agendadorEditado, setAgendadorEditado] = useState(false);
  const [chaveAdmin, setChaveAdmin] = useState('');
  const [atualizarExcel, setAtualizarExcel] = useState(false);
  const [escopoMensagens, setEscopoMensagens] = useState<EscopoMensagensTeste>('nenhum');
  const [forcarReenvioTeste, setForcarReenvioTeste] = useState(false);
  const [confirmarExecucao, setConfirmarExecucao] = useState(false);
  const [carregandoPrevia, setCarregandoPrevia] = useState(false);
  const [previaEnvio, setPreviaEnvio] = useState<PreviaEnvio | null>(null);
  const [automacaoStatus, setAutomacaoStatus] = useState({
    id: null as string | null,
    executando: false,
    estado: 'aguardando',
    inicio: null as string | null,
    fim: null as string | null,
    duracao_segundos: null as number | null,
    codigo_saida: null as number | null,
    erro: null as string | null,
    atualizou_excel: false,
    logs: [] as string[],
  });
  const [historicoExecucoes, setHistoricoExecucoes] = useState<HistoricoExecucao[]>([]);
  const execucaoEmAndamentoRef = useRef(false);

  useEffect(() => {
    if (!isOpen) return;
    const chaveSalva = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO);
    if (chaveSalva) setChaveAdmin(chaveSalva);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && activeTab === 'agendador') setAgendadorEditado(false);
  }, [isOpen, activeTab]);

  useEffect(() => {
    if (!isOpen || activeTab !== 'agendador' || !chaveAdmin) return;

    const carregarStatus = async () => {
      try {
        const resposta = await fetch('/api/automacao/agendador-status', {
          headers: { 'X-Admin-Key': chaveAdmin },
          cache: 'no-store',
        });
        if (resposta.ok) {
          const status = await resposta.json();
          setAgendadorStatus(status);
          if (!agendadorEditado) {
            setPrimeiroHorarioAgendador(status.horarios?.[0] || '09:00');
            setSegundoHorarioAgendador(status.horarios?.[1] || '14:00');
            setExcelAgendador(status.atualizar_excel === true);
            setNotificacoesTesteAgendador(status.notificacoes_teste === true);
          }
        }
      } catch {
        // O aviso visual das demais acoes continua disponivel no modal.
      }
    };

    carregarStatus();
    const intervalo = window.setInterval(carregarStatus, 10000);
    return () => window.clearInterval(intervalo);
  }, [isOpen, activeTab, chaveAdmin, agendadorEditado]);

  useEffect(() => {
    if (!isOpen || activeTab !== 'automacao' || !chaveAdmin) return;
    const carregarHistorico = async () => {
      const resposta = await fetch('/api/automacao/historico', {
        headers: { 'X-Admin-Key': chaveAdmin },
        cache: 'no-store',
      });
      if (resposta.ok) {
        const conteudo = await resposta.json();
        setHistoricoExecucoes(conteudo.execucoes || []);
      }
    };
    const carregarAutomacao = async () => {
      try {
        const resposta = await fetch('/api/automacao/status', {
          headers: { 'X-Admin-Key': chaveAdmin },
          cache: 'no-store',
        });
        if (resposta.ok) {
          const novoStatus = await resposta.json();
          const concluiuAgora =
            execucaoEmAndamentoRef.current &&
            !novoStatus.executando &&
            novoStatus.codigo_saida !== null;

          execucaoEmAndamentoRef.current = novoStatus.executando;
          setAutomacaoStatus(novoStatus);

          if (concluiuAgora) {
            await carregarHistorico();
            setMessage(
              novoStatus.codigo_saida === 0
                ? 'Automacao concluida. Dados do painel atualizados.'
                : 'Automacao encerrada com falha. Consulte os logs.',
            );
            setMessageType(novoStatus.codigo_saida === 0 ? 'success' : 'error');
          }
        }
      } catch {
        // Mantem o ultimo estado conhecido quando o backend estiver reiniciando.
      }
    };
    carregarAutomacao();
    carregarHistorico().catch(() => undefined);
    const intervalo = window.setInterval(carregarAutomacao, 3000);
    return () => window.clearInterval(intervalo);
  }, [isOpen, activeTab, chaveAdmin]);

  useEffect(() => {
    if (!isOpen || activeTab !== 'whatsapp' || !chaveAdmin) return;
    const carregarWhatsContabil = async () => {
      try {
        const resposta = await fetch('/api/whatscontabil/status', {
          headers: { 'X-Admin-Key': chaveAdmin },
          cache: 'no-store',
        });
        if (resposta.ok) setWhatsContabilStatus(await resposta.json());
      } catch {
        // A validacao manual mostrara uma mensagem mais detalhada.
      }
    };
    carregarWhatsContabil();
  }, [isOpen, activeTab, chaveAdmin]);

  if (!isOpen) return null;

  const showMessage = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
  };

  const atualizarChaveAdmin = (valor: string) => {
    setChaveAdmin(valor);
    if (valor) {
      window.sessionStorage.setItem(CHAVE_ADMIN_SESSAO, valor);
    } else {
      window.sessionStorage.removeItem(CHAVE_ADMIN_SESSAO);
    }
  };

  const abrirPreviaExecucao = async () => {
    if (!chaveAdmin.trim()) {
      showMessage('Informe a chave administrativa.', 'error');
      return;
    }

    setCarregandoPrevia(true);
    setPreviaEnvio(null);
    try {
      const resposta = await fetch('/api/certificados', { cache: 'no-store' });
      if (!resposta.ok) throw new Error('Nao foi possivel carregar a previa.');
      const certificados = await resposta.json();
      if (!Array.isArray(certificados)) throw new Error('Dados invalidos na previa.');

      const ativos = certificados.filter((item) => item?.ativo !== false);
      const vencendo = ativos.filter((item) => {
        const dias = item?.dias_para_vencimento;
        return Number.isInteger(dias) && dias >= 1 && dias <= 30;
      });
      const possuiValor = (valor: unknown) => String(valor ?? '').trim().length > 0;

      setPreviaEnvio({
        certificadosAviso: vencendo.length,
        avisosCliente: vencendo.filter((item) => possuiValor(item?.telefone_contato)).length,
        pendenciasEquipe: ativos.filter(
          (item) => !possuiValor(item?.telefone_contato) || !possuiValor(item?.email_contato),
        ).length,
        totalCertificados: ativos.length,
      });
      setConfirmarExecucao(true);
    } catch (erro) {
      showMessage(
        erro instanceof Error ? erro.message : 'Falha ao preparar a previa.',
        'error',
      );
    } finally {
      setCarregandoPrevia(false);
    }
  };

  const executarAutomacaoIntegrada = async () => {
    if (!chaveAdmin.trim()) {
      showMessage('Informe a chave administrativa.', 'error');
      return;
    }
    setConfirmarExecucao(false);
    setLoading(true);
    try {
      const resposta = await fetch('/api/automacao/executar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': chaveAdmin,
        },
        body: JSON.stringify({
          atualizar_excel: atualizarExcel,
          notificacoes_teste: escopoMensagens !== 'nenhum',
          escopo_notificacoes_teste: escopoMensagens,
          forcar_reenvio_teste: forcarReenvioTeste,
        }),
      });
      const conteudo = await resposta.json();
      if (!resposta.ok) throw new Error(conteudo.erro || 'Falha ao iniciar');
      showMessage('Automacao iniciada em segundo plano.');
      execucaoEmAndamentoRef.current = true;
      window.dispatchEvent(new Event(EVENTO_AUTOMACAO_ALTERADA));
      if (conteudo.status) {
        setAutomacaoStatus(conteudo.status);
      } else {
        setAutomacaoStatus((atual) => ({
          ...atual,
          executando: true,
          estado: 'executando',
          fim: null,
          codigo_saida: null,
          erro: null,
        }));
      }
    } catch (erro) {
      showMessage(erro instanceof Error ? erro.message : 'Falha ao iniciar', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailConfigSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('/api/notificacao/configurar-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emailConfig)
      });

      if (response.ok) {
        showMessage('Configurações de e-mail salvas com sucesso!');
      } else {
        const error = await response.json();
        showMessage(error.erro || 'Erro ao salvar configurações', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleWhatsappConfigSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('/api/notificacao/configurar-whatsapp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(whatsappConfig)
      });

      if (response.ok) {
        showMessage('Configurações do WhatsApp salvas com sucesso!');
      } else {
        const error = await response.json();
        showMessage(error.erro || 'Erro ao salvar configurações', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDestinatariosSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const emails = destinatarios.emails.filter(email => email.trim());
      const telefones = destinatarios.telefones.filter(tel => tel.trim());
      
      const response = await fetch('/api/notificacao/configurar-destinatarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emails, telefones })
      });

      if (response.ok) {
        showMessage('Destinatários configurados com sucesso!');
      } else {
        const error = await response.json();
        showMessage(error.erro || 'Erro ao salvar destinatários', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const testarEmail = async () => {
    if (!emailConfig.usuario) {
      showMessage('Configure o e-mail primeiro', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/notificacao/teste-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          destinatario: emailConfig.usuario,
          timestamp: new Date().toLocaleString('pt-BR')
        })
      });

      if (response.ok) {
        showMessage('E-mail de teste enviado com sucesso!');
      } else {
        const error = await response.json();
        showMessage(error.erro || 'Erro ao enviar e-mail de teste', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const testarWhatsapp = async () => {
    const telefone = destinatarios.telefones.find(tel => tel.trim());
    if (!telefone) {
      showMessage('Configure um telefone primeiro', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/notificacao/teste-whatsapp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero: telefone })
      });

      if (response.ok) {
        showMessage('Mensagem de teste enviada com sucesso!');
      } else {
        const error = await response.json();
        showMessage(error.erro || 'Erro ao enviar mensagem de teste', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const validarWhatsContabil = async () => {
    if (!chaveAdmin.trim()) {
      showMessage('Informe a chave administrativa.', 'error');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch('/api/whatscontabil/validar', {
        method: 'POST',
        headers: { 'X-Admin-Key': chaveAdmin },
      });
      const conteudo = await response.json();
      if (!response.ok) throw new Error(conteudo.erro || 'Falha na validacao');
      setWhatsContabilStatus(conteudo);
      showMessage(conteudo.mensagem || 'Integracao validada com sucesso!');
    } catch (erro) {
      showMessage(
        erro instanceof Error ? erro.message : 'Erro de conexao',
        'error',
      );
    } finally {
      setLoading(false);
    }
  };

  const configurarAgendador = async (ativo: boolean) => {
    if (!chaveAdmin.trim()) {
      showMessage('Informe a chave administrativa.', 'error');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch('/api/automacao/agendador-configurar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': chaveAdmin,
        },
        body: JSON.stringify({
          ativo,
          horarios: [primeiroHorarioAgendador, segundoHorarioAgendador],
          atualizar_excel: excelAgendador,
          notificacoes_teste: notificacoesTesteAgendador,
        }),
      });

      const conteudo = await response.json();
      if (response.ok) {
        showMessage(ativo ? 'Agendador ativado com sucesso!' : 'Agendador desativado.');
        setAgendadorStatus(conteudo.status);
        setPrimeiroHorarioAgendador(conteudo.status.horarios?.[0] || '09:00');
        setSegundoHorarioAgendador(conteudo.status.horarios?.[1] || '14:00');
        setExcelAgendador(conteudo.status.atualizar_excel === true);
        setNotificacoesTesteAgendador(conteudo.status.notificacoes_teste === true);
        setAgendadorEditado(false);
      } else {
        showMessage(conteudo.erro || 'Erro ao configurar agendador', 'error');
      }
    } catch {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const addEmail = () => {
    setDestinatarios(prev => ({
      ...prev,
      emails: [...prev.emails, '']
    }));
  };

  const addTelefone = () => {
    setDestinatarios(prev => ({
      ...prev,
      telefones: [...prev.telefones, '']
    }));
  };

  const removeEmail = (index: number) => {
    setDestinatarios(prev => ({
      ...prev,
      emails: prev.emails.filter((_, i) => i !== index)
    }));
  };

  const removeTelefone = (index: number) => {
    setDestinatarios(prev => ({
      ...prev,
      telefones: prev.telefones.filter((_, i) => i !== index)
    }));
  };

  const updateEmail = (index: number, value: string) => {
    setDestinatarios(prev => ({
      ...prev,
      emails: prev.emails.map((email, i) => i === index ? value : email)
    }));
  };

  const updateTelefone = (index: number, value: string) => {
    setDestinatarios(prev => ({
      ...prev,
      telefones: prev.telefones.map((tel, i) => i === index ? value : tel)
    }));
  };

  return (
    <div className="modal-backdrop fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="modal-panel bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <Settings className="w-5 h-5 mr-2" />
            Configurações do Sistema
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        {message && (
          <div className={`mx-6 mt-4 px-4 py-3 rounded ${
            messageType === 'success' 
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {message}
          </div>
        )}

        <div className="flex flex-wrap border-b">
          {[
            { id: 'automacao', label: 'Automacao', icon: Activity },
            { id: 'email', label: 'E-mail', icon: Mail },
            { id: 'whatsapp', label: 'WhatsContabil', icon: MessageCircle },
            { id: 'destinatarios', label: 'Destinatários', icon: Settings },
            { id: 'agendador', label: 'Agendador', icon: Play },
            { id: 'integracoes', label: 'Integrações', icon: HeartPulse }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center px-6 py-3 text-sm font-medium border-b-2 ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'email' && (
            <form onSubmit={handleEmailConfigSubmit} className="space-y-4">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Configuração de E-mail</h4>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Servidor SMTP
                  </label>
                  <input
                    type="text"
                    value={emailConfig.smtp_server}
                    onChange={(e) => setEmailConfig(prev => ({ ...prev, smtp_server: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="smtp.gmail.com"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Porta SMTP
                  </label>
                  <input
                    type="number"
                    value={emailConfig.smtp_port}
                    onChange={(e) => setEmailConfig(prev => ({ ...prev, smtp_port: parseInt(e.target.value) }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="587"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    E-mail
                  </label>
                  <input
                    type="email"
                    value={emailConfig.usuario}
                    onChange={(e) => setEmailConfig(prev => ({ ...prev, usuario: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="seu@email.com"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Senha
                  </label>
                  <input
                    type="password"
                    value={emailConfig.senha}
                    onChange={(e) => setEmailConfig(prev => ({ ...prev, senha: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Senha ou App Password"
                  />
                </div>
              </div>

              <div className="flex space-x-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Salvar Configurações
                </button>
                
                <button
                  type="button"
                  onClick={testarEmail}
                  disabled={loading}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
                >
                  <TestTube className="w-4 h-4 mr-2" />
                  Testar E-mail
                </button>
              </div>
            </form>
          )}

          {activeTab === 'whatsapp' && (
            <div className="space-y-5">
              <div>
                <h4 className="text-lg font-medium text-gray-900">Integracao WhatsContabil</h4>
                <p className="mt-1 text-sm text-gray-600">
                  Consulte a conexao oficial e os templates sem enviar mensagens.
                  O token permanece protegido no arquivo .env do backend.
                </p>
              </div>

              <label className="block text-sm text-gray-700">
                Chave administrativa
                <input
                  type="password"
                  value={chaveAdmin}
                  onChange={(evento) => atualizarChaveAdmin(evento.target.value)}
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                  placeholder="Informe a chave para consultar a integracao"
                />
              </label>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-xs uppercase tracking-wide text-gray-500">Configuracao</p>
                  <p className="mt-2 text-sm text-gray-700">
                    URL: {whatsContabilStatus.url_configurada ? 'configurada' : 'ausente'}
                  </p>
                  <p className="text-sm text-gray-700">
                    Token: {whatsContabilStatus.token_configurado ? 'configurado' : 'ausente'}
                  </p>
                  <p className="text-sm text-gray-700">Modo: {whatsContabilStatus.modo}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-xs uppercase tracking-wide text-gray-500">Canal</p>
                  <p className="mt-2 text-sm text-gray-700">
                    WhatsApp ID: {whatsContabilStatus.whatsapp_id || 'nao informado'}
                  </p>
                  <p className="text-sm text-gray-700">
                    Numero de teste: {whatsContabilStatus.numero_teste || 'nao informado'}
                  </p>
                </div>
              </div>

              {whatsContabilStatus.conectado && whatsContabilStatus.conexao && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                  <p className="font-medium text-green-800">Conexao oficial ativa</p>
                  <p className="mt-1 text-sm text-green-700">
                    {whatsContabilStatus.conexao.nome || 'Sem nome'} - {whatsContabilStatus.conexao.status}
                  </p>
                  <p className="text-sm text-green-700">
                    {whatsContabilStatus.quantidade_templates ?? 0} template(s) encontrado(s)
                  </p>
                </div>
              )}

              <button
                type="button"
                onClick={validarWhatsContabil}
                disabled={loading || !chaveAdmin.trim()}
                className="flex items-center rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <TestTube className="mr-2 h-4 w-4" />
                {loading ? 'Validando...' : 'Validar integracao'}
              </button>
            </div>
          )}

          {false && activeTab === 'whatsapp' && (
            <form onSubmit={handleWhatsappConfigSubmit} className="space-y-4">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Configuração do WhatsApp</h4>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Token da API
                  </label>
                  <input
                    type="text"
                    value={whatsappConfig.token}
                    onChange={(e) => setWhatsappConfig(prev => ({ ...prev, token: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Token do WhatsApp Business API"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Phone Number ID
                  </label>
                  <input
                    type="text"
                    value={whatsappConfig.phone_id}
                    onChange={(e) => setWhatsappConfig(prev => ({ ...prev, phone_id: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="ID do número de telefone"
                  />
                </div>
              </div>

              <div className="flex space-x-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Salvar Configurações
                </button>
                
                <button
                  type="button"
                  onClick={testarWhatsapp}
                  disabled={loading}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
                >
                  <TestTube className="w-4 h-4 mr-2" />
                  Testar WhatsApp
                </button>
              </div>
            </form>
          )}

          {activeTab === 'destinatarios' && (
            <form onSubmit={handleDestinatariosSubmit} className="space-y-6">
              <h4 className="text-lg font-medium text-gray-900">Destinatários das Notificações</h4>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  E-mails para Alertas
                </label>
                {destinatarios.emails.map((email, index) => (
                  <div key={index} className="flex mb-2">
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => updateEmail(index, e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-l-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="email@exemplo.com"
                    />
                    <button
                      type="button"
                      onClick={() => removeEmail(index)}
                      className="px-3 py-2 bg-red-500 text-white rounded-r-lg hover:bg-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addEmail}
                  className="text-blue-600 hover:text-blue-700 text-sm"
                >
                  + Adicionar E-mail
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Telefones para WhatsApp
                </label>
                {destinatarios.telefones.map((telefone, index) => (
                  <div key={index} className="flex mb-2">
                    <input
                      type="tel"
                      value={telefone}
                      onChange={(e) => updateTelefone(index, e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-l-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="(11) 99999-9999"
                    />
                    <button
                      type="button"
                      onClick={() => removeTelefone(index)}
                      className="px-3 py-2 bg-red-500 text-white rounded-r-lg hover:bg-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addTelefone}
                  className="text-blue-600 hover:text-blue-700 text-sm"
                >
                  + Adicionar Telefone
                </button>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
              >
                <Save className="w-4 h-4 mr-2" />
                Salvar Destinatários
              </button>
            </form>
          )}

          {activeTab === 'automacao' && (
            <div className="space-y-6">
              <h4 className="text-lg font-medium text-gray-900">Automacao de Certificados</h4>

              <div className="rounded-lg border border-gray-200 p-4 space-y-4">
                <div>
                  <h5 className="font-medium text-gray-900">Execucao manual</h5>
                  <p className="mt-1 text-sm text-gray-600">
                    Le os certificados, consulta os clientes e atualiza este site.
                    O envio de mensagens pode ser ativado abaixo sem depender do agendador.
                  </p>
                </div>
                <label className="block text-sm text-gray-700">
                  Chave administrativa
                  <input
                    type="password"
                    value={chaveAdmin}
                    onChange={(evento) => atualizarChaveAdmin(evento.target.value)}
                    autoComplete="off"
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                    placeholder="Informe a chave para executar"
                  />
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={atualizarExcel}
                    onChange={(evento) => setAtualizarExcel(evento.target.checked)}
                  />
                  Atualizar tambem a copia do Excel
                </label>
                <fieldset className="whatsapp-scope-panel rounded-xl border p-3 text-sm">
                  <legend className="px-1 font-medium">Mensagens WhatsContabil</legend>
                  <p className="whatsapp-safety-note mb-3 rounded-lg border px-3 py-2 text-xs">
                    Trava de seguranca ativa: todos os envios usam exclusivamente o numero de teste.
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {([
                      ['nenhum', 'Não enviar', 'Processa e sincroniza, sem mensagens.'],
                      ['relatorios', 'Somente relatórios', 'Envia os dois PDFs por link.'],
                      ['clientes', 'Somente clientes', 'Testa apenas os avisos individuais.'],
                      ['completo', 'Fluxo completo', 'Relatórios primeiro e clientes depois.'],
                    ] as const).map(([valor, titulo, descricao]) => (
                      <label
                        key={valor}
                        className={`whatsapp-scope-option cursor-pointer rounded-lg border p-3 transition-colors ${escopoMensagens === valor ? 'whatsapp-scope-option-selected shadow-sm ring-1 ring-blue-500/20' : ''}`}
                      >
                        <span className="flex items-start gap-2">
                          <input
                            type="radio"
                            name="escopo-mensagens"
                            value={valor}
                            checked={escopoMensagens === valor}
                            onChange={() => {
                              setEscopoMensagens(valor);
                              if (valor === 'nenhum') setForcarReenvioTeste(false);
                            }}
                            className="mt-0.5 accent-blue-600"
                          />
                          <span>
                            <span className="block font-medium">{titulo}</span>
                            <span className="whatsapp-scope-description mt-0.5 block text-xs">{descricao}</span>
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                  {escopoMensagens !== 'nenhum' && (
                    <label className="whatsapp-resend-warning mt-3 flex items-start gap-2 rounded-lg border p-3 text-xs">
                      <input
                        type="checkbox"
                        checked={forcarReenvioTeste}
                        onChange={(evento) => setForcarReenvioTeste(evento.target.checked)}
                        className="mt-0.5 accent-red-600"
                      />
                      <span>
                        <span className="block font-medium">Reenviar alertas já registrados</span>
                        Deixe desmarcado normalmente. Ative somente quando quiser repetir deliberadamente um teste.
                      </span>
                    </label>
                  )}
                </fieldset>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={abrirPreviaExecucao}
                    disabled={loading || carregandoPrevia || automacaoStatus.executando}
                    className="flex items-center rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    <Play className="mr-2 h-4 w-4" />
                    {automacaoStatus.executando
                      ? 'Executando...'
                      : carregandoPrevia
                        ? 'Preparando previa...'
                        : 'Executar agora'}
                  </button>
                  <span className={`text-sm font-medium ${automacaoStatus.executando ? 'text-blue-600' : automacaoStatus.codigo_saida === 0 ? 'text-green-600' : automacaoStatus.erro ? 'text-red-600' : 'text-gray-600'}`}>
                    {automacaoStatus.executando
                      ? 'Processamento em andamento'
                      : automacaoStatus.codigo_saida === 0
                        ? 'Ultima execucao concluida'
                        : automacaoStatus.erro || 'Aguardando execucao'}
                  </span>
                </div>
                {confirmarExecucao && !automacaoStatus.executando && (
                  <div className="automation-preview rounded-lg border p-4 text-sm">
                    <p className="font-semibold">Previa da execucao</p>
                    {previaEnvio && (
                      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <div className="automation-preview-card rounded-lg p-2">
                          <p className="automation-preview-label text-xs">Certificados</p>
                          <p className="text-lg font-semibold">{previaEnvio.totalCertificados}</p>
                        </div>
                        <div className="automation-preview-card rounded-lg p-2">
                          <p className="automation-preview-label text-xs">Entre 1 e 30 dias</p>
                          <p className="text-lg font-semibold">{previaEnvio.certificadosAviso}</p>
                        </div>
                        <div className="automation-preview-card rounded-lg p-2">
                          <p className="automation-preview-label text-xs">Com telefone</p>
                          <p className="text-lg font-semibold">{previaEnvio.avisosCliente}</p>
                        </div>
                        <div className="automation-preview-card rounded-lg p-2">
                          <p className="automation-preview-label text-xs">Contato pendente</p>
                          <p className="text-lg font-semibold">{previaEnvio.pendenciasEquipe}</p>
                        </div>
                      </div>
                    )}
                    <p className="mt-2 text-xs">
                      Estimativa baseada nos dados atualmente sincronizados. A automacao validara novamente os certificados e contatos antes do envio.
                    </p>
                    <ul className="mt-2 space-y-1 [&>li:last-child]:hidden">
                      <li>• Certificados e clientes serão consultados.</li>
                      <li>• Atualização do Excel: {atualizarExcel ? 'ativada' : 'desativada'}.</li>
                      <li>• E-mails e WhatsContábil: desativados nesta execução manual.</li>
                    </ul>
                    <p className="mt-1">
                      Mensagens pela WhatsContabil: {escopoMensagens === 'nenhum' ? 'desativadas' : `${escopoMensagens}, somente para o numero de teste`}.
                      {forcarReenvioTeste && escopoMensagens !== 'nenhum' ? ' Reenvio de duplicados autorizado para este teste.' : ''}
                    </p>
                    {escopoMensagens !== 'nenhum' && (
                      <div className="automation-preview-details mt-2 rounded-lg border px-3 py-2 text-xs">
                        <p className="font-medium">Itens previstos neste escopo:</p>
                        <p>{['relatorios', 'completo'].includes(escopoMensagens) ? 'Relatorio do responsavel e relatorio de pendencias da equipe.' : 'Nenhum relatorio.'}</p>
                        <p>{['clientes', 'completo'].includes(escopoMensagens) ? `Ate ${previaEnvio?.avisosCliente ?? 0} avisos individuais de cliente.` : 'Nenhum aviso individual de cliente.'}</p>
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => setConfirmarExecucao(false)}
                        className="rounded-lg bg-white px-3 py-2 font-medium text-gray-700 hover:bg-gray-100"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={executarAutomacaoIntegrada}
                        disabled={loading}
                        className="rounded-lg bg-blue-600 px-3 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        Confirmar execução
                      </button>
                    </div>
                  </div>
                )}
                {automacaoStatus.executando && (
                  <div className="space-y-1">
                    <div className="h-2 overflow-hidden rounded-full bg-blue-100">
                      <div className="h-full w-full animate-pulse rounded-full bg-blue-500" />
                    </div>
                    <p className="text-xs text-gray-500">
                      O andamento e atualizado aqui sem recarregar a pagina.
                    </p>
                  </div>
                )}
                {automacaoStatus.inicio && (
                  <div className="grid grid-cols-1 gap-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600 sm:grid-cols-3">
                    <p><span className="font-medium">Inicio:</span> {formatarDataHora(automacaoStatus.inicio)}</p>
                    <p><span className="font-medium">Fim:</span> {formatarDataHora(automacaoStatus.fim)}</p>
                    <p><span className="font-medium">Duracao:</span> {formatarDuracao(automacaoStatus.duracao_segundos)}</p>
                  </div>
                )}
                {automacaoStatus.logs.length > 0 && (
                  <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
                    {automacaoStatus.logs.slice(-30).join('\n')}
                  </pre>
                )}
              </div>

              <div className="rounded-lg border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h5 className="font-medium text-gray-900">Historico recente</h5>
                  <span className="text-xs text-gray-500">Ultimas 20 execucoes</span>
                </div>
                {historicoExecucoes.length === 0 ? (
                  <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
                    Nenhuma execucao concluida foi registrada ainda.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {historicoExecucoes.map((execucao) => (
                      <div
                        key={execucao.id}
                        className="grid grid-cols-1 gap-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600 sm:grid-cols-5"
                      >
                        <p>
                          <span className="block font-medium text-gray-800">Resultado</span>
                          <span className={execucao.estado === 'concluida' ? 'text-green-600' : 'text-red-600'}>
                            {execucao.estado === 'concluida' ? 'Concluida' : 'Falhou'}
                          </span>
                        </p>
                        <p>
                          <span className="block font-medium text-gray-800">Inicio</span>
                          {formatarDataHora(execucao.inicio)}
                        </p>
                        <p>
                          <span className="block font-medium text-gray-800">Duracao</span>
                          {formatarDuracao(execucao.duracao_segundos)}
                        </p>
                        <p>
                          <span className="block font-medium text-gray-800">Excel</span>
                          {execucao.atualizou_excel ? 'Atualizado' : 'Nao solicitado'}
                        </p>
                        <p>
                          <span className="block font-medium text-gray-800">Avisos</span>
                          {execucao.notificacoes_teste ? 'Teste enviado' : 'Desativados'}
                        </p>
                        {execucao.erro && (
                          <p className="text-red-600 sm:col-span-5">{execucao.erro}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'integracoes' && (
            <div className="space-y-5">
              <div>
                <h4 className="text-lg font-medium text-gray-900">Saúde das integrações</h4>
                <p className="mt-1 text-sm text-gray-600">
                  Confira o estado dos serviços usados pela automação sem enviar mensagens ou alterar dados.
                </p>
              </div>

              <label className="block text-sm text-gray-700">
                Chave administrativa
                <input
                  type="password"
                  value={chaveAdmin}
                  onChange={(evento) => atualizarChaveAdmin(evento.target.value)}
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                  placeholder="Informe a chave para verificar"
                />
              </label>

              <IntegrationHealthPanel chaveAdmin={chaveAdmin} embutido />
            </div>
          )}

          {activeTab === 'agendador' && (
            <div className="space-y-6">
              <h4 className="text-lg font-medium text-gray-900">Controle do Agendador</h4>

              <label className="block text-sm text-gray-700">
                Chave administrativa
                <input
                  type="password"
                  value={chaveAdmin}
                  onChange={(evento) => atualizarChaveAdmin(evento.target.value)}
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                  placeholder="Informe a chave para configurar"
                />
              </label>

              <div className="grid grid-cols-1 gap-4 rounded-lg border border-gray-200 p-4 sm:grid-cols-2 lg:grid-cols-4">
                <label className="text-sm text-gray-700">
                  Primeiro horario
                  <input
                    type="time"
                    value={primeiroHorarioAgendador}
                    onChange={(evento) => {
                      setPrimeiroHorarioAgendador(evento.target.value);
                      setAgendadorEditado(true);
                    }}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                  />
                </label>
                <label className="text-sm text-gray-700">
                  Segundo horario
                  <input
                    type="time"
                    value={segundoHorarioAgendador}
                    onChange={(evento) => {
                      setSegundoHorarioAgendador(evento.target.value);
                      setAgendadorEditado(true);
                    }}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                  />
                </label>
                <label className="flex items-center gap-2 self-end rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={excelAgendador}
                    onChange={(evento) => {
                      setExcelAgendador(evento.target.checked);
                      setAgendadorEditado(true);
                    }}
                  />
                  Atualizar tambem a copia do Excel
                </label>
                <label className="flex items-center gap-2 self-end rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  <input
                    type="checkbox"
                    checked={notificacoesTesteAgendador}
                    onChange={(evento) => {
                      setNotificacoesTesteAgendador(evento.target.checked);
                      setAgendadorEditado(true);
                    }}
                  />
                  Enviar avisos ao numero de teste
                </label>
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                No modo de teste, somente a WhatsContabil sera acionada e todas as mensagens
                irao para o numero de teste configurado. O envio de e-mails permanece bloqueado.
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h5 className="font-medium text-gray-900 mb-2">Status Atual</h5>
                <div className="space-y-2 text-sm text-gray-600">
                  <p>Status: <span className={`font-medium ${agendadorStatus.ativo ? 'text-green-600' : 'text-red-600'}`}>
                    {agendadorStatus.ativo ? 'Ativo' : 'Desativado'}
                  </span></p>
                  <p>Monitor interno: {agendadorStatus.monitorando ? 'funcionando' : 'parado'}</p>
                  <p>Horarios configurados: {agendadorStatus.horarios.join(' e ')}</p>
                  <p>Notificacoes de teste: {agendadorStatus.notificacoes_teste ? 'ativadas' : 'desativadas'}</p>
                  <p>Proxima execucao: {formatarDataHora(agendadorStatus.proxima_execucao)}</p>
                  <p>Ultima execucao agendada: {formatarDataHora(agendadorStatus.ultima_execucao)}</p>
                  {agendadorStatus.ativo && (
                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border border-green-200 bg-green-50 p-3">
                        <p className="text-xs text-green-700">Executadas hoje</p>
                        <p className="mt-1 font-semibold text-green-800">{agendadorStatus.execucoes_hoje?.length || 0}/2</p>
                        <p className="mt-1 text-xs text-green-700">{agendadorStatus.execucoes_hoje?.join(', ') || 'Nenhuma ainda'}</p>
                      </div>
                      <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                        <p className="text-xs text-blue-700">Pendentes hoje</p>
                        <p className="mt-1 font-semibold text-blue-800">{agendadorStatus.horarios_pendentes?.length || 0}</p>
                        <p className="mt-1 text-xs text-blue-700">{agendadorStatus.horarios_pendentes?.join(', ') || 'Nenhuma'}</p>
                      </div>
                      <div className={`rounded-lg border p-3 ${agendadorStatus.horarios_atrasados?.length ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'}`}>
                        <p className={`text-xs ${agendadorStatus.horarios_atrasados?.length ? 'text-red-700' : 'text-gray-500'}`}>Atrasadas</p>
                        <p className={`mt-1 font-semibold ${agendadorStatus.horarios_atrasados?.length ? 'text-red-700' : 'text-gray-800'}`}>{agendadorStatus.horarios_atrasados?.length || 0}</p>
                        <p className={`mt-1 text-xs ${agendadorStatus.horarios_atrasados?.length ? 'text-red-700' : 'text-gray-500'}`}>{agendadorStatus.horarios_atrasados?.join(', ') || 'Tudo dentro do horario'}</p>
                      </div>
                    </div>
                  )}
                  {agendadorStatus.situacao === 'monitor_parado' && <p className="font-medium text-red-600">Atencao: agendador ativo, mas o monitor interno esta parado.</p>}
                  {agendadorStatus.situacao === 'atrasado' && <p className="font-medium text-red-600">Atencao: existe uma execucao diaria atrasada.</p>}
                  {agendadorStatus.ultimo_erro && (
                    <p className="text-red-600">Erro: {agendadorStatus.ultimo_erro}</p>
                  )}
                </div>
              </div>

              <div className="flex space-x-4">
                <button
                  onClick={() => configurarAgendador(true)}
                  disabled={
                    loading ||
                    !chaveAdmin.trim() ||
                    !primeiroHorarioAgendador ||
                    !segundoHorarioAgendador ||
                    primeiroHorarioAgendador === segundoHorarioAgendador
                  }
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Salvar e ativar
                </button>
                
                <button
                  onClick={() => configurarAgendador(false)}
                  disabled={loading || !chaveAdmin.trim()}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Desativar
                </button>
              </div>
              {agendadorEditado && (
                <p className="text-sm font-medium text-amber-600">
                  Existem alteracoes ainda nao salvas.
                </p>
              )}

              <div className="hidden">
                <h5 className="font-medium text-blue-900 mb-2">Horários de Verificação</h5>
                <ul className="text-sm text-blue-800 space-y-1">
                  <li>• 09:00 - Verificação completa (certificados vencendo em 30 dias)</li>
                  <li>• 14:00 - Verificação urgente (certificados vencendo em 15 dias)</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

