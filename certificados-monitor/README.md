# Monitor de certificados - backend

## Preparar o ambiente

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha somente no arquivo local. Nunca
adicione `.env`, tokens, credenciais, certificados, PDFs ou bancos SQLite ao Git.

## Rodar os testes

Na pasta `certificados-monitor`:

```powershell
python -m pytest
```

Os testes usam banco em memória, arquivos temporários e mocks. Eles não devem
enviar e-mails, mensagens da WhatsContábil ou executar as automações reais.

O teste manual que envia um resumo fictício está separado em
`scripts/testar_resumo_atualizacoes_email.py` e só deve ser executado quando um
envio for autorizado.
