# Empório da Música

Protótipo de atendimento para uma loja fictícia de instrumentos musicais.

**Status:** estrutura inicial. O agente, a importação, a sessão demonstrativa e
os modelos de negócio ainda não foram implementados. Nenhuma integração com LLM
é simulada como funcional.

## Stack

- Backend: Python 3.12, Django 5.2, Django REST Framework.
- Documentação: OpenAPI e Swagger UI com drf-spectacular.
- Frontend: Next.js, React e TypeScript.
- Banco: PostgreSQL 17, gerenciado por migrations Django.
- Inferência: Ollama, com modelo ainda a selecionar e validar.
- Execução local: Docker Compose.

## Estrutura

```text
backend/          Configuração Django, apps por domínio e testes
frontend/         Aplicação Next.js com App Router
db/               Orientações de persistência
ollama/           Orientações para o runtime e modelos
docker/           Dockerfiles e orientações dos containers
data/private/     Arquivos originais, ignorados pelo Git
data/synthetic/   Fixtures públicas a implementar
docs/             Arquitetura e decisões compartilháveis
scripts/          Automação auxiliar
```

## Execução local planejada

Pré-requisitos: Docker com Compose v2 e recursos compatíveis com o futuro modelo.
O conjunto completo de containers ainda não foi validado nesta etapa.

1. Copiar `.env.example` para `.env`.
2. Preencher `DJANGO_SECRET_KEY` e `POSTGRES_PASSWORD` com valores locais fortes.
   Para gerar um valor: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. Executar `docker compose up --build -d`.
4. Executar `docker compose exec backend python manage.py migrate`.
5. Verificar os serviços com `docker compose ps`.

O frontend usa a porta local 3000; o backend, 8000. Rotas da API:

- `GET /api/health/`: liveness do processo; não comprova prontidão do banco/modelo.
- `GET /api/schema/`: esquema OpenAPI.
- `GET /api/docs/`: Swagger UI.

Ollama inicia sem modelo baixado. Consulte `ollama/README.md` antes de configurar
`OLLAMA_MODEL`. Não será possível conversar com um agente nesta etapa.

Para parar: `docker compose down`. Os volumes são preservados. Não usar `down -v`
se desejar manter banco e modelos.

## Dados e decisões

Não versionar os CSVs de clientes, arquivos originais, credenciais, banco ou
pesos do modelo. O importador e as fixtures sintéticas serão implementados depois.
Veja `docs/architecture.md` para responsabilidades e políticas de interpretação.

## Desenvolvimento e entrega

Trabalho em `develop`; commits somente após revisão e autorização do responsável.
O primeiro commit permitirá criar também `main`. Merge para `main` e publicação
serão feitos pelo responsável. Não alterar a entrega após o prazo do processo.

## Uso de IA

OpenAI Codex está sendo usado na discussão de arquitetura, análise dos dados e
criação assistida da estrutura. As decisões são alinhadas com o candidato.
Esta seção será atualizada para refletir implementação e validações efetivamente
realizadas. Limitações, conversas demonstrativas e instruções finais serão
consolidadas nas próximas etapas.
