# Empório da Música

Protótipo de atendimento para uma loja fictícia de instrumentos musicais.

**Status:** camada de dados, ferramentas, índice de políticas e orquestração do
agente por CLI implementados. A geração real está pendente de validação com Docker
na máquina do desenvolvedor após bloqueios de rede e quedas do ambiente na nuvem.
Sessão web e interface de chat ainda não foram
implementadas. Nenhuma integração com LLM é simulada como funcional.

## Stack

- Backend: Python 3.12, Django 5.2, Django REST Framework.
- Documentação: OpenAPI e Swagger UI com drf-spectacular.
- Frontend: Next.js, React e TypeScript.
- Banco: PostgreSQL 17, gerenciado por migrations Django.
- Inferência: Ollama local; candidato `qwen3:4b`, ainda sem validação de geração.
- Execução local: Docker Compose.

## Estrutura

```text
backend/          Configuração Django, apps por domínio e testes
frontend/         Aplicação Next.js com App Router
db/               Orientações de persistência
ollama/           Orientações para o runtime e modelos
docker/           Dockerfiles e orientações dos containers
data/private/     Arquivos originais, ignorados pelo Git
data/synthetic/   CSVs e PDF sintéticos para reprodução pública
docs/             Arquitetura e decisões compartilháveis
scripts/          Automação auxiliar
```

## Execução local

Pré-requisitos: Docker com Compose v2 e recursos compatíveis com o futuro modelo.
O conjunto completo, incluindo frontend e modelo, ainda não foi validado.

1. Copiar `.env.example` para `.env`.
2. Preencher `DJANGO_SECRET_KEY` e `POSTGRES_PASSWORD` com valores locais fortes.
   Para gerar um valor: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. Executar `docker compose up --build -d`.
4. Executar `docker compose exec backend python manage.py migrate`.
5. Em um banco vazio, importar os exemplos públicos:
   `docker compose exec backend python manage.py import_store_data --directory /data/synthetic`.
6. Verificar os serviços com `docker compose ps`.

O frontend usa a porta local 3000; o backend, 8000. Rotas da API:

- `GET /api/health/`: liveness do processo; não comprova prontidão do banco/modelo.
- `GET /api/schema/`: esquema OpenAPI.
- `GET /api/docs/`: Swagger UI.

Ollama inicia sem modelo baixado. Consulte `docs/agent.md` para importar o PDF,
baixar o modelo e usar o CLI. Conversas exigem download e configuração do modelo.
A validação com modelo real será realizada localmente com Docker.

Para parar: `docker compose down`. Os volumes são preservados. Não usar `down -v`
se desejar manter banco e modelos.

## Dados e decisões

Não versionar os CSVs de clientes, arquivos originais, credenciais, banco ou
pesos do modelo. Há fixtures inteiramente sintéticas em `data/synthetic`.
Use bancos separados para originais e exemplos: os IDs de origem podem coincidir.
Veja `docs/data-import.md` para validação, reimportação e limitações, e
`docs/architecture.md` para responsabilidades e políticas de interpretação.

## Validação do backend

```sh
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py test tests --noinput
```

A suíte usa fixtures sintéticas e um banco de teste separado. O usuário PostgreSQL
de desenvolvimento precisa de permissão para criar esse banco. Nunca executar
testes apontando para uma configuração de produção.

`backend/requirements.txt` declara intervalos; `backend/requirements.lock.txt`
fixa as versões usadas pelo Docker e pelas validações. Atualize o lock de forma
deliberada, reexecutando os testes.

## Desenvolvimento e entrega

Trabalho em `develop`; commits somente após revisão e autorização do responsável.
As branches `main` e `develop` já existem. Merge para `main` e publicação só
ocorrem mediante orientação do responsável. Não alterar a entrega após o prazo
do processo.

## Uso de IA

Sou responsável pelas decisões técnicas, pela definição da arquitetura e pelo
planejamento deste projeto. Defino as prioridades e a direção da solução,
avaliando as recomendações apresentadas durante o desenvolvimento.

Utilizo o OpenAI Codex como meu agente de IA para auxiliar na implementação das
ideias e dos planos que aprovo. Esse apoio inclui análise dos dados, discussão de
alternativas técnicas, geração de código, documentação e verificações. Mantenho
a responsabilidade pela revisão e aprovação das entregas e pelas decisões finais.
