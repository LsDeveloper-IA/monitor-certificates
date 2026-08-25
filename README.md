# Projeto Monitoramento Certificados Digitais

## Integração com a automação

O backend recebe os certificados processados pelo endpoint autenticado:

```http
POST /api/certificados/sincronizar
X-API-Key: valor-de-INTEGRACAO_API_KEY
Content-Type: application/json
```

Exemplo de corpo:

```json
{
  "certificados": [
    {
      "empresa": "Empresa Exemplo",
      "cnpj": "12345678000190",
      "vencimento": "2027-05-05",
      "email": "contato@example.com",
      "telefone": "5585000000000",
      "responsavel": "Responsável",
      "arquivo": "certificado.pfx",
      "observacao": "Processado pela automação"
    }
  ]
}
```

O CPF/CNPJ é normalizado e usado como identificador. Uma nova execução
atualiza o cadastro existente em vez de criar duplicatas. Esse endpoint não
envia e-mails ou mensagens.

Copie `certificados-monitor/.env.example` para `.env` e defina chaves fortes
antes de iniciar o backend.
