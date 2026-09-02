# Automação SIEG — modular com lógica preservada

Esta versão divide o código em módulos, mas preserva exatamente os corpos das funções da versão de arquivo único.

## Estrutura

```text
ProjetoOfficeModularPreservado/
├── main.py
├── automacao.py
├── sieg_service.py
├── drive_service.py
├── utilitarios.py
├── persistencia.py
├── config.py
├── __init__.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Responsabilidades

| Arquivo | Conteúdo |
| --- | --- |
| `main.py` | Inicialização e tentativas completas. |
| `automacao.py` | Fluxo principal de processamento. |
| `sieg_service.py` | Funções de interação com o SIEG. |
| `drive_service.py` | Autenticação, arquivos, certificados e Google Docs. |
| `utilitarios.py` | Normalização, CNPJ e validade do certificado. |
| `persistencia.py` | Checkpoint, evidências de erro e resumo da execução. |
| `config.py` | Constantes, caminhos e leitura do `.env`. |

## Configuração

Preencha o arquivo `.env`:

```env
SIEG_EMAIL=seu-email
SIEG_SENHA=sua-senha
```

Coloque `credentials.json` na mesma pasta. Se já existir um `token.pickle` autorizado, copie-o também.

## Instalação

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Execução

```bash
python main.py
```

## Acréscimos mantidos

- Credenciais do SIEG pelo `.env`.
- Senha do certificado em Google Docs nativo.
- Até três tentativas para erros não tratados.
- Caminhos de autenticação relativos à pasta do projeto.
- Confirmação do CNPJ da linha antes do upload do certificado.
- Validação explícita da mensagem de sucesso ou erro da senha do certificado.
- Retomada automática dos CNPJs concluídos no mesmo dia.
- Foto e HTML da tela em cada falha, além de resumo detalhado ao final.
- Resumo JSON com a quantidade de empresas do Drive não listadas no SIEG (`certas`).
- Índice em memória das pastas do Drive, criado uma vez por execução.
- Cache do resultado de cada pasta do Drive para evitar consultas repetidas.
- Tentativa sequencial dos certificados de todas as pastas com similaridade de
  nome igual ou superior a 85%, sempre priorizando nomes exatos.
- Quando existe correspondência de 100%, as pastas com pontuação inferior não
  são lidas nem testadas.
- Razões sociais abreviadas são tratadas como equivalentes quando dois ou mais
  termos distintivos formam exatamente o início do nome completo.
- Esperas inteligentes baseadas em elementos visíveis, carregamento da rede,
  modais, tabelas, campos e indicadores de processamento.

## Otimizações de execução

Ao iniciar, a automação lista a pasta raiz do Google Drive uma única vez e cria
um índice de nomes normalizados. Durante o processamento, pastas exatas ou com
pelo menos 85% de similaridade são testadas da maior para a menor pontuação.
O resultado da leitura de cada pasta também fica em cache durante a execução.

As pausas fixas da interface foram substituídas por esperas condicionais do
Playwright. O programa continua assim que o estado esperado aparece e gera uma
falha por timeout quando a tela não chega ao estado necessário. A única espera
fixa restante é o intervalo entre tentativas completas em `main.py`, pois ela
representa a política de retentativa e não o carregamento da interface.

## Retomada e relatórios

Durante a execução, o programa cria automaticamente a pasta `registros/`:

```text
registros/
├── checkpoint.json
├── resumo_AAAAMMDD_HHMMSS.txt
└── erros/
    ├── erro_CNPJ_DATA_HORA.png
    └── erro_CNPJ_DATA_HORA.html
```

O `checkpoint.json` registra cada CNPJ somente depois que todo o fluxo da empresa termina com sucesso. Se o programa cair e for iniciado novamente no mesmo dia, esses CNPJs serão pulados. No dia seguinte, um novo checkpoint diário começa automaticamente.

Depois de preencher a senha do certificado, a automação espera por até 30 segundos por uma mensagem explícita do SIEG. Se o candidato for rejeitado, ela volta à tabela, reabre a mesma empresa e testa o próximo candidato de alta similaridade. A empresa só é registrada como falha depois que todos os candidatos forem rejeitados ou quando nenhuma confirmação aparecer.

O arquivo `resumo_*.txt` contém totais, CNPJs, nomes, motivos das falhas e caminhos das respectivas evidências.

## Garantia de preservação

A divisão move apenas as funções para arquivos responsáveis e acrescenta os imports necessários. Os corpos das funções são comparados automaticamente com o `Pronto.py` de referência para garantir que seletores, cliques, tempos, condições e ordem do fluxo não mudaram.

## Segurança

O `.env`, `credentials.json` e `token.pickle` estão no `.gitignore` e não devem ser enviados ao GitHub.
