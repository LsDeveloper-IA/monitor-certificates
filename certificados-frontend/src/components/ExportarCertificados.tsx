'use client';

import { useState } from 'react';
import { Dialog, DialogPanel, DialogTitle } from '@headlessui/react';
import { Download, X } from 'lucide-react';

const COLUNAS = [
  ['nome_empresa', 'Empresa / cliente'], ['cpf_cnpj', 'CPF / CNPJ'],
  ['responsavel', 'Responsável'], ['data_vencimento', 'Vencimento'],
  ['dias', 'Dias para vencer'], ['status', 'Situação'],
  ['email_contato', 'E-mail'], ['telefone_contato', 'Telefone'],
  ['tipo', 'Tipo de pessoa'], ['arquivo_drive_id', 'Arquivo do certificado'],
];

export default function ExportarCertificados({ idsFiltrados, total }: { idsFiltrados: number[]; total: number }) {
  const [aberto, setAberto] = useState(false);
  const [colunas, setColunas] = useState(COLUNAS.slice(0, 8).map(c => c[0]));
  const [escopo, setEscopo] = useState('filtrados');
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const quantidade = escopo === 'todos' ? total : idsFiltrados.length;

  async function exportar() {
    setCarregando(true); setErro('');
    try {
      const parametros = new URLSearchParams({ colunas: COLUNAS.filter(c => colunas.includes(c[0])).map(c => c[0]).join(',') });
      if (escopo === 'filtrados') parametros.set('ids', idsFiltrados.join(','));
      const resposta = await fetch(`/api/certificados/exportar-excel?${parametros}`, { cache: 'no-store' });
      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}));
        throw new Error(dados.erro || 'Não foi possível exportar. Tente novamente.');
      }
      const blob = await resposta.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `certificados_${new Date().toLocaleDateString('sv-SE')}.xlsx`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setAberto(false);
    } catch (e) { setErro(e instanceof Error ? e.message : 'Falha de conexão. Tente novamente.'); }
    finally { setCarregando(false); }
  }
  return <>
    <button type="button" disabled={!total} onClick={() => { setAberto(true); setErro(''); }} className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"><Download size={16} />Exportar Excel</button>
    <Dialog open={aberto} onClose={() => { if (!carregando) setAberto(false); }} className="relative z-[60]">
      <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel className="modal-panel w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 text-gray-900 shadow-xl">
          <div className="flex items-center justify-between gap-3"><DialogTitle className="text-lg font-semibold">Exportar certificados</DialogTitle><button type="button" disabled={carregando} onClick={() => setAberto(false)} aria-label="Fechar exportação" className="p-2 text-gray-500"><X size={20} /></button></div>
          <fieldset disabled={carregando} className="mt-5 space-y-3"><legend className="text-sm font-medium mb-2">Quais certificados?</legend>
            <label className="flex gap-2 items-center text-sm"><input type="radio" name="escopo-exportacao" checked={escopo === 'filtrados'} onChange={() => setEscopo('filtrados')} />Resultados dos filtros ({idsFiltrados.length})</label>
            <label className="flex gap-2 items-center text-sm"><input type="radio" name="escopo-exportacao" checked={escopo === 'todos'} onChange={() => setEscopo('todos')} />Todos os certificados ({total})</label>
            <p className="text-xs text-gray-500">Inclui todas as páginas dos resultados selecionados.</p>
          </fieldset>
          <fieldset disabled={carregando} className="mt-5"><legend className="text-sm font-medium">Colunas da planilha</legend>
            <div className="flex gap-4 my-3 text-xs text-blue-600"><button type="button" onClick={() => setColunas(COLUNAS.map(c => c[0]))}>Selecionar todas</button><button type="button" onClick={() => setColunas([])}>Limpar seleção</button></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{COLUNAS.map(([id, nome]) => <label key={id} className="flex gap-2 items-center text-sm"><input type="checkbox" checked={colunas.includes(id)} onChange={e => setColunas(atual => e.target.checked ? [...atual, id] : atual.filter(c => c !== id))} />{nome}</label>)}</div>
          </fieldset>
          {erro && <p role="alert" className="mt-4 text-sm text-red-600">{erro}</p>}
          <p aria-live="polite" className="mt-5 text-sm text-gray-500">{quantidade} certificados · {colunas.length} colunas</p>
          <div className="mt-4 flex justify-end gap-3"><button type="button" disabled={carregando} onClick={() => setAberto(false)} className="rounded-lg px-3 py-2 text-sm text-gray-600">Cancelar</button><button type="button" disabled={carregando || !colunas.length || !quantidade} onClick={exportar} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"><Download size={16} />{carregando ? 'Gerando Excel…' : 'Baixar Excel'}</button></div>
        </DialogPanel>
      </div>
    </Dialog>
  </>;
}
