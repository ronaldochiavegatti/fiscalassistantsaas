# Fiscal Assistant SaaS

Este repositório documenta uma arquitetura mínima em microserviços para um MVP focado em assistentes fiscais. A proposta prioriza simplicidade, separação de responsabilidades e componentes prontos para crescer com o produto.

## Visão Geral

- **api-gateway**: termina TLS, roteia para `/auth`, `/documents`, `/limits`, `/assistant` e `/billing`. Injeta `X-Request-ID` para rastreabilidade.
- **auth-service**: cadastro/login, refresh tokens e RBAC básico (user, admin). Tabelas sugeridas: `users`, `sessions` (opcional) e `plans`.
- **documents-service**: upload, listagem e edição de campos extraídos. Fluxo: upload → metadados no Postgres → arquivo no Oracle Object Storage → job de OCR enfileirado no Celery. Tabelas sugeridas: `documents`, `document_extractions`, `transactions` (opcional para unificação de eventos).
- **limits-service**: consolida faturamento mensal/anual e calcula limite restante do MEI (81k). Expõe endpoints para Dashboard e Assistant. Pode consumir eventos do documents-service (via Redis/Celery) ou ler diretamente as `transactions`.
- **assistant-service (RAG)**: recebe pergunta + `user_id`, consulta Postgres/pgvector para montar contexto e chama a LLM. Usa dados de `transactions` para responder perguntas como “quanto faturei mês passado?”.
- **billing-service**: controla assinatura (Free/Pro/Enterprise), contagem de tokens e limites de upload. Integração futura com gateway de pagamento pode ficar stub no MVP.
- **reflex-frontend**: páginas de Landing, Dashboard, Documents, AI Assistant, Billing/Settings e Admin. Comunica-se apenas com o api-gateway.

## Executando o MVP da Fase 1

### auth-service

```bash
cd auth-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### api-gateway

```bash
cd api-gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
JWT_SECRET=super-secret-key uvicorn main:app --reload --port 8000
```

### reflex-frontend

Abra `reflex-frontend/index.html` no navegador para ver a landing page com cards do dashboard mockados. A chamada “Começar agora” leva diretamente ao painel.

## Infraestrutura Compartilhada

- **Postgres**: schemas separados por serviço (se desejado).
- **Redis**: broker/result backend do Celery e cache simples.
- **Celery worker**: executa OCR do documents-service, agregações e tarefas recorrentes.
- **Celery beat**: agenda jobs, por exemplo recálculo diário de limites.

## Próximos Passos Recomendados

1. Definir contratos de API (OpenAPI) para cada serviço.
2. Especificar eventos/filas principais entre documents-service e limits-service.
3. Versionar schemas do Postgres por serviço (ex.: usando Alembic) para facilitar evolução.
4. Configurar observabilidade básica: logs estruturados com `X-Request-ID`, métricas e traces de ponta a ponta via api-gateway.
