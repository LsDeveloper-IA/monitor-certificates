'use client';

import { useState } from 'react';
import { X, Save, Mail, MessageCircle, TestTube, Play, Pause, Settings } from 'lucide-react';

interface ConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ConfigModal({ isOpen, onClose }: ConfigModalProps) {
  const [activeTab, setActiveTab] = useState('email');
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
  const [whatsappConfig, setWhatsappConfig] = useState({
    token: '',
    phone_id: ''
  });

  // Estados para destinatários
  const [destinatarios, setDestinatarios] = useState({
    emails: [''],
    telefones: ['']
  });

  // Estados para agendador
  const [agendadorStatus, setAgendadorStatus] = useState({
    executando: false,
    emails_configurados: 0,
    telefones_configurados: 0,
    proximas_execucoes: []
  });

  if (!isOpen) return null;

  const showMessage = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
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
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
      showMessage('Erro de conexão', 'error');
    } finally {
      setLoading(false);
    }
  };

  const controlarAgendador = async (acao: 'iniciar' | 'parar') => {
    setLoading(true);
    try {
      const response = await fetch(`/api/notificacao/agendador/${acao}`, {
        method: 'POST'
      });

      if (response.ok) {
        showMessage(`Agendador ${acao === 'iniciar' ? 'iniciado' : 'parado'} com sucesso!`);
        // Atualizar status
      } else {
        const error = await response.json();
        showMessage(error.erro || `Erro ao ${acao} agendador`, 'error');
      }
    } catch (error) {
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto">
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

        <div className="flex border-b">
          {[
            { id: 'email', label: 'E-mail', icon: Mail },
            { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
            { id: 'destinatarios', label: 'Destinatários', icon: Settings },
            { id: 'agendador', label: 'Agendador', icon: Play }
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

          {activeTab === 'agendador' && (
            <div className="space-y-6">
              <h4 className="text-lg font-medium text-gray-900">Controle do Agendador</h4>
              
              <div className="bg-gray-50 p-4 rounded-lg">
                <h5 className="font-medium text-gray-900 mb-2">Status Atual</h5>
                <div className="space-y-2 text-sm text-gray-600">
                  <p>Status: <span className={`font-medium ${agendadorStatus.executando ? 'text-green-600' : 'text-red-600'}`}>
                    {agendadorStatus.executando ? 'Executando' : 'Parado'}
                  </span></p>
                  <p>E-mails configurados: {agendadorStatus.emails_configurados}</p>
                  <p>Telefones configurados: {agendadorStatus.telefones_configurados}</p>
                </div>
              </div>

              <div className="flex space-x-4">
                <button
                  onClick={() => controlarAgendador('iniciar')}
                  disabled={loading}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Iniciar Agendador
                </button>
                
                <button
                  onClick={() => controlarAgendador('parar')}
                  disabled={loading}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Parar Agendador
                </button>
              </div>

              <div className="bg-blue-50 p-4 rounded-lg">
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

