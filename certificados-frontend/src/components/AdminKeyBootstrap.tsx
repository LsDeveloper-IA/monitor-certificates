'use client';

import { useEffect } from 'react';

const CHAVE_ADMIN_SESSAO = 'certificados-monitor:chave-admin';
const EVENTO_AUTOMACAO_ALTERADA = 'certificados-monitor:automacao-alterada';

/**
 * Preenche a chave administrativa no pacote portatil.
 *
 * A busca so e ativada quando o build define
 * NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN=1. No servidor tradicional o componente
 * nao faz nada e o usuario continua digitando a chave em Configuracoes.
 */
export default function AdminKeyBootstrap() {
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN !== '1') return;

    let cancelado = false;
    fetch('/api/configuracao/chave-admin', {
      cache: 'no-store',
      credentials: 'same-origin',
    })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => {
        if (cancelado || !dados?.chave) return;

        const atual = window.sessionStorage.getItem(CHAVE_ADMIN_SESSAO) || '';
        // Uma chave digitada pelo usuario tem prioridade. A chave local e
        // atualizada quando ainda nao existe ou veio do preenchimento antigo.
        if (atual && atual !== 'local') return;

        window.sessionStorage.setItem(CHAVE_ADMIN_SESSAO, String(dados.chave));
        window.dispatchEvent(new Event(EVENTO_AUTOMACAO_ALTERADA));
      })
      .catch(() => {
        // O painel continua funcionando; o usuario pode informar a chave
        // manualmente em Configuracoes se necessario.
      });

    return () => {
      cancelado = true;
    };
  }, []);

  return null;
}
