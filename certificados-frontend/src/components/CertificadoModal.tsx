'use client';

import { useState } from 'react';
import { X, Save, Building, User } from 'lucide-react';

interface CertificadoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (certificado: CertificadoFormData & { id?: number }) => void;
  certificado?: Partial<CertificadoFormData> & { id: number };
}

interface CertificadoFormData {
  nome_empresa: string;
  cpf_cnpj: string;
  tipo: 'PJ' | 'PF';
  data_vencimento: string;
  responsavel: string;
  email_contato: string;
  telefone_contato: string;
  observacoes: string;
}

export default function CertificadoModal({ isOpen, onClose, onSave, certificado }: CertificadoModalProps) {
  const [formData, setFormData] = useState<CertificadoFormData>({
    nome_empresa: certificado?.nome_empresa || '',
    cpf_cnpj: certificado?.cpf_cnpj || '',
    tipo: certificado?.tipo || 'PJ',
    data_vencimento: certificado?.data_vencimento || '',
    responsavel: certificado?.responsavel || '',
    email_contato: certificado?.email_contato || '',
    telefone_contato: certificado?.telefone_contato || '',
    observacoes: certificado?.observacoes || ''
  });

  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Limpa erro do campo quando usuário começa a digitar
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.nome_empresa.trim()) {
      newErrors.nome_empresa = 'Nome/Empresa é obrigatório';
    }

    if (!formData.cpf_cnpj.trim()) {
      newErrors.cpf_cnpj = 'CPF/CNPJ é obrigatório';
    }

    if (!formData.data_vencimento) {
      newErrors.data_vencimento = 'Data de vencimento é obrigatória';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setLoading(true);
    try {
      const url = certificado 
        ? `/api/certificados/${certificado.id}`
        : '/api/certificados';
      
      const method = certificado ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const data = await response.json();
        onSave(data);
        onClose();
      } else {
        const errorData = await response.json();
        setErrors({ submit: errorData.erro || 'Erro ao salvar certificado' });
      }
    } catch {
      setErrors({ submit: 'Erro de conexão. Tente novamente.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <h3 className="text-lg font-semibold text-gray-900">
            {certificado ? 'Editar Certificado' : 'Novo Certificado'}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {errors.submit && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {errors.submit}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tipo de Pessoa
              </label>
              <div className="flex space-x-4">
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="tipo"
                    value="PJ"
                    checked={formData.tipo === 'PJ'}
                    onChange={handleChange}
                    className="mr-2"
                  />
                  <Building className="w-4 h-4 mr-1" />
                  Pessoa Jurídica
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="tipo"
                    value="PF"
                    checked={formData.tipo === 'PF'}
                    onChange={handleChange}
                    className="mr-2"
                  />
                  <User className="w-4 h-4 mr-1" />
                  Pessoa Física
                </label>
              </div>
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Nome/Empresa *
              </label>
              <input
                type="text"
                name="nome_empresa"
                value={formData.nome_empresa}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  errors.nome_empresa ? 'border-red-300' : 'border-gray-300'
                }`}
                placeholder={formData.tipo === 'PJ' ? 'Nome da empresa' : 'Nome completo'}
              />
              {errors.nome_empresa && (
                <p className="text-red-600 text-sm mt-1">{errors.nome_empresa}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {formData.tipo === 'PJ' ? 'CNPJ' : 'CPF'} *
              </label>
              <input
                type="text"
                name="cpf_cnpj"
                value={formData.cpf_cnpj}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  errors.cpf_cnpj ? 'border-red-300' : 'border-gray-300'
                }`}
                placeholder={formData.tipo === 'PJ' ? '00.000.000/0001-00' : '000.000.000-00'}
              />
              {errors.cpf_cnpj && (
                <p className="text-red-600 text-sm mt-1">{errors.cpf_cnpj}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Data de Vencimento *
              </label>
              <input
                type="date"
                name="data_vencimento"
                value={formData.data_vencimento}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  errors.data_vencimento ? 'border-red-300' : 'border-gray-300'
                }`}
              />
              {errors.data_vencimento && (
                <p className="text-red-600 text-sm mt-1">{errors.data_vencimento}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Responsável
              </label>
              <input
                type="text"
                name="responsavel"
                value={formData.responsavel}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Nome do responsável"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                E-mail de Contato
              </label>
              <input
                type="email"
                name="email_contato"
                value={formData.email_contato}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="email@exemplo.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Telefone de Contato
              </label>
              <input
                type="tel"
                name="telefone_contato"
                value={formData.telefone_contato}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="(11) 99999-9999"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Observações
              </label>
              <textarea
                name="observacoes"
                value={formData.observacoes}
                onChange={handleChange}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Observações adicionais..."
              />
            </div>
          </div>

          <div className="flex justify-end space-x-4 pt-6 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {loading ? 'Salvando...' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

