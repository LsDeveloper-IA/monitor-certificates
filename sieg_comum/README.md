# Integrações Compartilhadas do SIEG

Pacote Python usado por `automacao-sieg` e `Auto_NC`. Ele concentra operações
que antes existiam em duplicidade e não inicia navegador nem carrega `.env` ao
ser importado.

## Módulos

| Arquivo | Responsabilidade |
| --- | --- |
| `sessao.py` | Login no SIEG e reconhecimento de sessão autenticada. |
| `navegacao.py` | Esperas, clique com rolagem, edição de empresa e preenchimento de UF. |
| `modais.py` | Diálogo visível, botões e campos de upload por semântica. |
| `drive.py` | OAuth, paginação, downloads, Google Docs, senhas e busca de pastas. |
| `identidade.py` | Normalização de nomes e documentos. |
| `certificados.py` | Leitura e validação local dos certificados. |
| `configuracao.py` | Conversão validada de opções numéricas do ambiente. |

## Contratos

- Cada automação carrega seu próprio `.env` e passa valores ao pacote.
- A credencial do Google é persistida em `token.json` por
  `Credentials.to_json()` e lida por `from_authorized_user_file()`.
- Senhas em TXT, DOCX e Google Docs passam pela mesma limpeza de conteúdo.
- `preencher_uf(page, uf)` aceita as 27 siglas brasileiras, preenche somente
  campos vazios e retorna `False` quando a interação falha.
- A busca no Drive mantém as políticas de correspondência definidas por cada
  automação.
- Controles de upload ficam restritos ao diálogo ativo.

As opções `Docs Fiscais/HUB`, `Controle de Pendências/Iris` e
`NFS-e Portal Nacional` são localizadas por rótulo. O campo inicial de
atualização ainda usa um caminho relativo, limitado ao diálogo visível.

## Uso

As duas entradas adicionam a raiz do repositório ao caminho de imports:

- `automacao-sieg/_bootstrap.py`
- `Auto_NC/main.py`

Por isso, mantenha `sieg_comum/` no mesmo nível das pastas das automações. O
pacote não possui processo independente.

## Testes

Na raiz do repositório:

```powershell
python -X utf8 -m unittest discover -s sieg_comum/tests
```

Os testes de navegador usam Chromium headless com HTML local. Testes do Drive
usam mocks e não alteram arquivos ou contas remotas.
