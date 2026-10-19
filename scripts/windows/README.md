# Atualizacao do servidor Windows

Instalacao em uso: `D:\Projetos\monitor-certificates`.
Servicos existentes: `MonitorCertificados` e `MonitorFrontend`.
Configuracao WinSW: `D:\Servicos\MonitorCertificados`.

## ODBC srvcontabil

No arquivo `D:\Projetos\monitor-certificates\certificados-monitor\.env`, configure:

```env
ODBC_DSN=srvcontabil
```

Esse valor e o **nome do DSN**, nao o nome do servidor/banco SQL Anywhere.
O DSN de Sistema de 64 bits deve existir e seu teste de conexao deve funcionar.
Renomear a configuracao nao resolve `Database server not found`.
Reinicie o backend depois de mudar o `.env`, parando o frontend antes quando
o Windows indicar que existe dependencia entre os servicos.
O workflow preserva o `.env`: ele nao altera esse valor no servidor remoto.

## Antes de ativar

1. Confirme que os dois servicos estao funcionando e a conta pode consultar
   o banco e o Drive. Instale Git, Python e Node 22 LTS no servidor.
2. Use uma conta de Windows dedicada para o runner. Ela precisa ler a
   instalacao e os XMLs do WinSW, escrever nos diretorios da aplicacao e de
   backup e parar/iniciar somente os dois servicos. Peça ao TI essas permissoes;
   nao conceda administrador ao runner como solucao padrao.
3. Restrinja quem pode enviar codigo para `automacao_certificados`. Proteja
   essa branch com revisao. Em repositorio publico, o GitHub desaconselha
   runners persistentes na rede da empresa: prefira um repositorio privado
   de implantacao. Nao rode workflows de pull requests externos nessa maquina.

## Cadastrar o runner (uma vez, no computador servidor)

No GitHub: **Settings > Actions > Runners > New self-hosted runner > Windows > x64**.
Se a opcao nao aparecer, um administrador do repositorio precisa cadastrar.

Crie `D:\GitHubRunner\monitor-certificados` e execute ali os comandos de download
e configuracao fornecidos pelo GitHub. O token de cadastro e temporario: use o
do painel, sem copia-lo para arquivos ou para o chat.

Durante a configuracao:

- Nome: `servidor-nexabi-monitor`.
- Additional labels: `monitor-certificados`.
- Work folder: `_work` (padrao).
- Run as service: `Y`.
- Conta do servico: a conta dedicada autorizada pelo TI.

Nao instale o runner dentro de `D:\Projetos\monitor-certificates`.
O checkout automatico fica em `_work` e pode ser limpo pelo GitHub. Nunca
coloque tokens Google, `.env`, certificados ou banco nessa pasta.

## Ativar as atualizacoes

O workflow `.github/workflows/windows-local.yml` deve estar publicado na branch
`automacao_certificados`. Para o botao **Run workflow** aparecer, o mesmo
workflow tambem precisa existir na branch padrao; nao e necessario mudar a
branch padrao nem fazer merge de outras funcionalidades para isso.

Em **Settings > Environments**, configure `windows-local` com deployment
branches limitado a `automacao_certificados`. Use aprovacao por responsavel,
se disponivel no plano do repositorio.

Em **Settings > Secrets and variables > Actions > Variables**, configure:

| Nome | Valor |
|---|---|
| `MONITOR_INSTALL_ROOT` | `D:\Projetos\monitor-certificates` |
| `DEPLOY_WINDOWS_ENABLED` | `true` somente depois que runner e permissoes estiverem prontos |

Sem `DEPLOY_WINDOWS_ENABLED=true`, somente os testes/build sao executados.
As credenciais de runtime ficam no servidor; nao precisam virar secrets do
GitHub. O runner le as chaves do `.env` e dos XMLs sem imprimi-las.

Depois de ativado, novos pushes na branch executam testes em Windows no GitHub.
Somente se passarem o job de atualizacao e liberado para o runner da empresa.
Para repetir apos uma automacao ocupada ou falha de rede, use **Re-run jobs**.

## O que a atualizacao faz

1. Consulta os status da automacao de certificados e do SIEG. Se estiverem
   executando, aborta sem interromper o processamento; nao espera indefinidamente.
2. Gera o build novo na pasta separada do runner, com o endereco do backend local.
3. Confere os status novamente e para os servicos para uma breve manutencao.
4. Guarda os arquivos substituidos e o build anterior em uma pasta
   `D:\Projetos\monitor-backup-DATA-COMMIT`.
5. Copia somente arquivos versionados do frontend/backend, instala dependencias
   e copia o build pronto. Nao roda a automacao, nao envia mensagens e nao consulta ODBC.
6. Inicia os servicos e verifica a pagina e o status autenticado das APIs.
7. Se falhar, tenta recuperar o codigo/build anterior e reinstalar as dependencias.
   Falhas de rede/disco/permissao tambem podem impedir a recuperacao: nesse caso,
   confira os logs e use o backup. Nao existem migracoes automaticas do banco.

Nao modifica `.env`, tokens, certificados, banco, runtime, relatorios nem os XMLs
dos servicos. Tambem nao atualiza `Auto_NC`, `automacao-sieg` ou `sieg_comum`:
essas pastas pertencem ao fluxo do colega. Arquivos obsoletos de codigo nao sao
apagados automaticamente; remocoes futuras precisam de revisao.

O backend pode retomar agendamentos ativos ao iniciar. Use uma janela fora dos
dois horarios configurados e evite iniciar uma automacao manual durante o deploy.
O historico e os backups precisam de acompanhamento de espaco em disco.
Nao use `git pull` na pasta de producao depois desse instalador: ela recebe
arquivos pelo deploy e o HEAD local nao e movido. O commit instalado fica
registrado no backup e no log do Actions. Para desenvolvimento use outro clone.

## Validacao local, sem deploy

```powershell
powershell -NoProfile -File scripts\windows\testar-deploy.ps1
```

Nao execute `atualizar.ps1` no computador de desenvolvimento: ele requer a
instalacao e os servicos reais da maquina da empresa.
