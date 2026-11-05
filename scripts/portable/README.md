# Pacote portatil do Monitor de Certificados

Gera um unico `MonitorCertificados.exe` (PyInstaller onefile) que inicia o
backend Flask com Waitress e serve o frontend Next.js em modo de exportacao
estatica. A maquina de destino **nao precisa de Node.js**.

## Como gerar

Requisitos no computador de build:

- Python 3.11+ com as dependencias de `certificados-monitor/requirements.txt`
- PyInstaller (`python -m pip install pyinstaller`)
- Node.js 20+ com `npm install` executado em `certificados-frontend/`

Na raiz do repositorio:

```powershell
.\scripts\portable\build.ps1
```

Etapas executadas pelo script:

1. roda a suite de testes (use `-SkipTests` para pular);
2. move temporariamente `certificados-frontend/src/app/api`, remove o `.next`
   anterior, define `NEXT_STATIC_EXPORT=1` e
   `NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN=1`, executa `npm run build` e restaura a
   pasta no `finally`;
3. copia `certificados-frontend/out/` para `build/portable/web`;
4. empacota `scripts/portable/entrypoint.py` com o spec
   `MonitorCertificados.spec`, incluindo a pasta `web` e o `.env.example`;
5. monta `monitor-certificates/` com o exe, o modelo de `.env`, o
   `LEIA-ME.txt` e uma pasta `storage/` vazia.

A pasta `monitor-certificates/` e versionada no Git, incluindo o executavel,
para que a versao pronta para uso acompanhe o repositorio. O `.env` e os dados
gerados em `storage/` continuam ignorados.

Opcoes uteis:

```powershell
# Reaproveitar o frontend ja compilado e nao rodar testes
.\scripts\portable\build.ps1 -SkipTests -SkipFrontend

# Reaproveitar o exe ja gerado e montar apenas a pasta final
.\scripts\portable\build.ps1 -SkipTests -SkipFrontend -SkipPyInstaller
```

## Como validar

O script de fumaca copia o exe para uma pasta temporaria, inicia o servidor,
valida a pagina inicial, a geracao do `.env`, a chave administrativa local,
leitura/escrita autenticada, o proxy local e o bloqueio de requisicoes sem
chave. O navegador nao e aberto.

```powershell
.\scripts\portable\testar-pacote.ps1
.\scripts\portable\testar-pacote.ps1 -Executavel .\monitor-certificates\MonitorCertificados.exe
```

Use `-Keep` para preservar a pasta temporaria e inspecionar `saida.log`,
`erro.log` e o `.env` gerado.

## Como funciona em tempo de execucao

- `entrypoint.py` cria o `.env` na primeira execucao substituindo os
  marcadores `__GERAR_...__` por chaves aleatorias.
- A porta preferida e `FLASK_PORT` (padrao 5000). Se estiver ocupada, o
  programa testa 5001 a 5099 e informa o endereco escolhido.
- `storage/` fica ao lado do `.env` e guarda banco, historicos, logs e
  segredos OAuth.
- O frontend consulta `/api/configuracao/chave-admin` para preencher a chave
  administrativa automaticamente. O endpoint so responde a requisicoes locais
  com origem local.
- As automacoes sao executadas por um Python externo. O executavel procura
  `MONITOR_PYTHON_EXE` ou `python` no `PATH`.

## Automacoes (opcional)

O painel funciona sem Python instalado; apenas a execucao das automacoes
depende dele. Na maquina de destino:

```powershell
pip install -r automacoes\sieg\requirements.txt
pip install -r automacoes\auto_nc\requirements.txt
pip install -r automacoes\conthabil\requirements.txt
python -m playwright install chromium
```

Copie a pasta `automacoes/` para o lado do executavel, mantendo os `.env` de
cada automacao. Os dados gerados continuam em `storage/` (ou no caminho
definido em `STORAGE_DIR`).

## Solucao de problemas

- **Falha ao iniciar**: veja `storage/logs/erro-inicializacao.log`.
- **Modulo nao encontrado em tempo de execucao**: confira se o pacote esta em
  `hiddenimports` no `MonitorCertificados.spec` e gere novamente.
- **Antivirus**: executaveis PyInstaller podem precisar de liberacao.
- **Banco em uso**: feche o painel antes de copiar `storage/database/app.db`.
