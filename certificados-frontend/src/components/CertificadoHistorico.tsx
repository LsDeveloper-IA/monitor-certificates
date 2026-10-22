'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Clock3, Paperclip, Save, X } from 'lucide-react';

interface Registro { id: number; autor: string; texto: string; criado_em: string; editado_em?: string; imagens: number[] }

function ImagemHistorico({ id }: { id: number }) {
  const [url, setUrl] = useState('');
  const [erro, setErro] = useState(false);
  useEffect(() => {
    const controle = new AbortController();
    let objeto = '';
    fetch(`/api/historico/imagens/${id}`, { signal: controle.signal })
      .then(async r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(blob => { objeto = URL.createObjectURL(blob); setUrl(objeto); })
      .catch(() => { if (!controle.signal.aborted) setErro(true); });
    return () => { controle.abort(); if (objeto) URL.revokeObjectURL(objeto); };
  }, [id]);
  if (erro) return <span className="text-sm text-red-600">Imagem indisponível. Reabra o histórico para tentar novamente.</span>;
  if (!url) return <span className="text-sm text-gray-500">Carregando imagem…</span>;
  return <a href={url} target="_blank" rel="noopener noreferrer" className="block rounded-lg border overflow-hidden focus-visible:ring-2 focus-visible:ring-blue-500" aria-label="Abrir imagem anexada em nova aba">
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={url} alt="Imagem anexada à observação" className="w-32 h-24 object-cover" />
  </a>;
}

export default function CertificadoHistorico({ certificadoId, ativo }: { certificadoId: number; ativo: boolean }) {
  const [autor, setAutor] = useState('');
  const [texto, setTexto] = useState('');
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [registros, setRegistros] = useState<Registro[]>([]);
  const [pagina, setPagina] = useState(1);
  const [temMais, setTemMais] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState('');
  const [sucesso, setSucesso] = useState('');
  const [tentativa, setTentativa] = useState(0);
  const [editando, setEditando] = useState<number | null>(null);
  const [edicao, setEdicao] = useState('');
  const [excluindo, setExcluindo] = useState<number | null>(null);
  const [alterando, setAlterando] = useState(false);
  const [erroAlteracao, setErroAlteracao] = useState('');
  const entradaArquivo = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setAutor(localStorage.getItem('historico:autor') || '');
  }, []);
  const carregar = useCallback(async (p: number, sinal?: AbortSignal) => {
    const r = await fetch(`/api/historico/certificados/${certificadoId}?pagina=${p}`, {
      signal: sinal, cache: 'no-store',
    });
    const dados = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(dados.erro || 'Não foi possível carregar o histórico. Tente novamente.');
    setRegistros(dados.registros); setTemMais(dados.tem_mais);
  }, [certificadoId]);
  useEffect(() => {
    if (!ativo) return;
    const controle = new AbortController();
    setCarregando(true); setErro('');
    carregar(pagina, controle.signal).catch(e => {
      if (!controle.signal.aborted) setErro(e.message);
    }).finally(() => { if (!controle.signal.aborted) setCarregando(false); });
    return () => controle.abort();
  }, [ativo, pagina, carregar, tentativa]);

  async function alterar(id: number, metodo: 'PUT' | 'DELETE') {
    if (alterando) return;
    setAlterando(true); setErroAlteracao(''); setSucesso('');
    try {
      const r = await fetch(`/api/historico/registros/${id}`, { method: metodo,
        ...(metodo === 'PUT' ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto: edicao }) } : {}) });
      const resposta = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(resposta.erro || 'Não foi possível alterar. Tente novamente.');
      setEditando(null); setExcluindo(null);
      setSucesso(metodo === 'PUT' ? 'Observação atualizada.' : 'Registro excluído.');
      if (metodo === 'DELETE' && registros.length === 1 && pagina > 1) setPagina(p => p - 1);
      setTentativa(n => n + 1);
    } catch (e) { setErroAlteracao(e instanceof Error ? e.message : 'Falha de conexão. Tente novamente.'); }
    finally { setAlterando(false); }
  }

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (salvando) return;
    setErro(''); setSucesso(''); setSalvando(true);
    const dados = new FormData();
    dados.append('autor', autor.trim()); dados.append('texto', texto.trim());
    arquivos.forEach(arquivo => dados.append('imagens', arquivo));
    try {
      const r = await fetch(`/api/historico/certificados/${certificadoId}`, { method: 'POST', body: dados });
      const resposta = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(resposta.erro || 'Não foi possível salvar. Sua observação foi mantida para tentar novamente.');
      try { localStorage.setItem('historico:autor', autor.trim()); } catch { /* O registro já foi salvo no servidor. */ }
      setTexto(''); setArquivos([]);
      if (entradaArquivo.current) entradaArquivo.current.value = '';
      setSucesso('Observação registrada.');
      setPagina(1); setTentativa(n => n + 1);
    } catch (e) { setErro(e instanceof Error ? e.message : 'Falha de conexão. Tente novamente.'); }
    finally { setSalvando(false); }
  }
  return <section className="p-6 space-y-6 text-gray-900">
    <div><h4 className="font-semibold">Acompanhamento do certificado</h4><p className="text-sm text-gray-500 mt-1">Registre contatos, retornos e outras observações. Os registros mais recentes aparecem primeiro.</p></div>
    <form onSubmit={salvar} className="space-y-4 rounded-lg border border-gray-200 p-4">
      <label className="block text-sm font-medium">Seu nome
        <input value={autor} onChange={e => setAutor(e.target.value)} maxLength={100} required className="mt-1 block w-full rounded-lg border px-3 py-2" placeholder="Quem está registrando esta observação?" />
      </label>
      <label className="block text-sm font-medium">Observação
        <textarea value={texto} onChange={e => setTexto(e.target.value)} required maxLength={5000} rows={3} className="mt-1 block w-full rounded-lg border px-3 py-2" placeholder="Ex.: Tentei entrar em contato, mas não consegui. Retornar amanhã." />
      </label>
      <div>
        <label htmlFor="historico-imagens" className="flex items-center gap-2 text-sm font-medium"><Paperclip size={16} />Anexar imagens</label>
        <p id="historico-limites" className="text-xs text-gray-500 mt-1 mb-2">Até 3 imagens JPG, PNG ou WebP de 5 MB cada. Evite anexar senhas e documentos sensíveis.</p>
        <input id="historico-imagens" aria-describedby="historico-limites" ref={entradaArquivo} type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={salvando} className="block w-full text-sm cursor-pointer" onChange={e => {
          const novos = [...arquivos, ...Array.from(e.target.files || [])];
          e.target.value = '';
          if (novos.length > 3 || novos.some(f => f.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(f.type))) {
            setErro('Selecione até 3 imagens JPG, PNG ou WebP, com no máximo 5 MB cada.'); return;
          }
          setArquivos(novos); setErro('');
        }} />
        <ul className="space-y-1 mt-2">{arquivos.map((f, i) => <li key={`${f.name}-${i}`} className="flex gap-2 items-center text-xs"><span className="min-w-0 truncate">{f.name}</span><button type="button" disabled={salvando} onClick={() => setArquivos(a => a.filter((_, n) => n !== i))} aria-label={`Remover ${f.name}`} className="p-2 cursor-pointer text-gray-500 hover:text-red-600"><X size={14} /></button></li>)}</ul>
      </div>
      <button type="submit" disabled={salvando || !autor.trim() || !texto.trim()} className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"><Save size={16} />{salvando ? 'Registrando…' : 'Registrar observação'}</button>
      <p className="text-xs text-gray-500">O nome é informado por você. Data e hora são registradas pelo sistema.</p>
    </form>
    {sucesso && <p role="status" className="text-sm text-green-600">{sucesso}</p>}
    {erroAlteracao && <p role="alert" className="text-sm text-red-600">{erroAlteracao}</p>}
    {erro && <div role="alert" className="text-sm text-red-600 space-y-2"><p>{erro}</p><button type="button" onClick={() => setTentativa(n => n + 1)} className="underline cursor-pointer">Tentar carregar novamente</button></div>}
    <div aria-busy={carregando} className="space-y-4" hidden={!!erro}>
      {carregando ? <p role="status" className="text-sm text-gray-500">Carregando histórico…</p> : !erro && registros.length === 0 ? <p className="text-sm text-gray-500 py-4">Nenhuma observação registrada neste certificado.</p> : registros.map(r => <article key={r.id} className="border border-gray-200 rounded-lg p-4 min-w-0">
        <header className="flex flex-wrap justify-between gap-2 text-sm"><span className="font-semibold break-all">{r.autor}</span><time dateTime={r.criado_em} className="text-xs text-gray-500 inline-flex items-center gap-1"><Clock3 size={13} />{new Date(r.criado_em).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })} (Brasília)</time></header>
        {r.editado_em && <p className="text-xs text-gray-500 mt-1">Editado em {new Date(r.editado_em).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })} (Brasília)</p>}
        {editando === r.id ? <div className="mt-3 space-y-2">
          <label className="block text-sm">Editar observação<textarea autoFocus value={edicao} onChange={e => setEdicao(e.target.value)} maxLength={5000} rows={4} disabled={alterando} className="block w-full border rounded-lg p-3 mt-1" /></label>
          <div className="flex gap-3"><button type="button" disabled={alterando || !edicao.trim()} onClick={() => alterar(r.id, 'PUT')} className="bg-blue-600 text-white rounded-lg px-3 py-2 text-sm disabled:opacity-50">{alterando ? 'Salvando…' : 'Salvar alterações'}</button><button type="button" disabled={alterando} onClick={() => setEditando(null)} className="text-sm text-gray-600">Cancelar</button></div>
        </div> : <p className="text-sm whitespace-pre-wrap break-words mt-3">{r.texto}</p>}
        {!!r.imagens.length && <div className="flex flex-wrap gap-2 mt-3">{r.imagens.map(id => <ImagemHistorico key={id} id={id} />)}</div>}
        {excluindo === r.id ? <div className="mt-3 border border-red-200 rounded-lg p-3 space-y-2">
          <p className="text-sm">Excluir esta observação e suas imagens? Esta ação não pode ser desfeita.</p>
          <div className="flex gap-3"><button type="button" disabled={alterando} onClick={() => alterar(r.id, 'DELETE')} className="bg-red-600 text-white rounded-lg px-3 py-2 text-sm disabled:opacity-50">{alterando ? 'Excluindo…' : 'Confirmar exclusão'}</button><button type="button" disabled={alterando} onClick={() => setExcluindo(null)} className="text-sm text-gray-600">Cancelar</button></div>
        </div> : editando !== r.id && <div className="flex gap-4 mt-3 text-sm"><button type="button" disabled={alterando} className="text-blue-600" onClick={() => { setEditando(r.id); setEdicao(r.texto); setExcluindo(null); setErroAlteracao(''); }}>Editar</button><button type="button" disabled={alterando} className="text-red-600" onClick={() => { setExcluindo(r.id); setEditando(null); setErroAlteracao(''); }}>Excluir</button></div>}
      </article>)}
    </div>
    {(pagina > 1 || temMais) && <nav aria-label="Páginas do histórico" className="flex items-center justify-between gap-2 text-sm"><button type="button" disabled={pagina === 1 || carregando} onClick={() => setPagina(p => p - 1)} className="border rounded-lg px-3 py-2 disabled:opacity-40 cursor-pointer">Mais recentes</button><span>Página {pagina}</span><button type="button" disabled={!temMais || carregando} onClick={() => setPagina(p => p + 1)} className="border rounded-lg px-3 py-2 disabled:opacity-40 cursor-pointer">Mais antigos</button></nav>}
  </section>;
}
