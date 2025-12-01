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

Variáveis úteis:
- `LIMITS_SERVICE_URL`: URL do limits_service (default `http://localhost:8003`).

### reflex-frontend

Abra `reflex-frontend/index.html` no navegador para ver a landing page. O dashboard consulta o `limits_service` e cai em fallback local caso o endpoint não esteja rodando.

### documents_service + Celery worker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r documents_service/requirements.txt

# API de upload (usa o mesmo banco sqlite ./saas.db por padrão)
uvicorn documents_service.main:app --reload --port 8002

# Worker para processar OCR / criar transações (broker Redis default)
CELERY_BROKER_URL=redis://localhost:6379/0 celery -A documents_service.worker.celery_app worker -l info
```

### limits_service

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r limits_service/requirements.txt
uvicorn limits_service.main:app --reload --port 8003
```

O endpoint `/limits/summary?year=2025&user_id=1` retorna:

- Receita do mês atual
- Receita anual acumulada
- Limite restante (81k - receita anual)

### billing_service

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r billing_service/requirements.txt
uvicorn billing_service.main:app --reload --port 8005
```

Endpoints:

- `POST /billing/track-usage`: registra tokens, uploads e chamadas.
- `GET /billing/me?user_id=1`: consulta o plano corrente (Free/Pro stub) e consumo do mês.

### assistant_service (RAG)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r assistant_service/requirements.txt
BILLING_SERVICE_URL=http://localhost:8005 uvicorn assistant_service.main:app --reload --port 8004
```

O endpoint `POST /assistant/chat` recebe `{ "user_id": 1, "message": "..." }`, consulta as transações recentes e monta um parecer textual. O serviço registra uso de tokens no billing_service automaticamente.

### reflex-frontend

A interface agora inclui:

- Dashboard com faturamento e alertas do limits_service.
- Widget de chat para o assistant_service.
- Cartão de consumo do billing_service.

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
