# Empório da Música

Protótipo de atendimento para uma loja fictícia de instrumentos musicais.

**Status:** camada de dados, ferramentas, índice de políticas e orquestração do
agente por CLI implementados. A validação local com `qwen3:1.7b` identificou falhas
de consulta e fidelidade; foram implementadas correções e proteções, ainda sem
aprovação definitiva do modelo. Veja `docs/agent.md` e os relatórios em `docs/validation`.
Sessão web e interface de chat ainda não foram
implementadas. Nenhuma integração com LLM é simulada como funcional.

## Stack

- Backend: Python 3.12, Django 5.2, Django REST Framework.
- Documentação: OpenAPI e Swagger UI com drf-spectacular.
- Frontend: Next.js, React e TypeScript.
- Banco: PostgreSQL 17, gerenciado por migrations Django.
- Inferência: Ollama local; `qwen3:1.7b` em avaliação. O `.env.example` mantém
  o candidato anterior `qwen3:4b`; configure o modelo instalado no ambiente local.
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
A validação com modelo real é executada localmente com Docker e dados sintéticos.

Para parar: `docker compose down`. Os volumes são preservados. Não usar `down -v`
se desejar manter banco e modelos.

## Dados e decisões

Optei por manter os CSVs originais de clientes, os demais arquivos originais,
as credenciais, o banco e os pesos do modelo fora do versionamento. Para permitir
a reprodução pública do projeto, disponibilizo fixtures inteiramente sintéticas
em `data/synthetic`.
Mantenho os dados originais e os exemplos em bancos separados, pois os IDs de
origem podem coincidir. Documento a validação, a reimportação e as limitações em
`docs/data-import.md`, e as responsabilidades e políticas de interpretação em
`docs/architecture.md`.

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

Trabalho na branch `develop` e reviso e autorizo os commits antes de realizá-los.
Mantenho a branch `main` para a entrega e decido quando fazer o merge e a
publicação. Após o prazo do processo seletivo, não faço alterações na entrega.

## Uso de IA

Sou responsável pelas decisões técnicas, pela definição da arquitetura e pelo
planejamento deste projeto. Defino as prioridades e a direção da solução,
avaliando as recomendações apresentadas durante o desenvolvimento.

Utilizo o OpenAI Codex como meu agente de IA para auxiliar na implementação das
ideias e dos planos que aprovo. Esse apoio inclui análise dos dados, discussão de
alternativas técnicas, geração de código, documentação e verificações. Mantenho
a responsabilidade pela revisão e aprovação das entregas e pelas decisões finais.
