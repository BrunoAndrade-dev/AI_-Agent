# API de atendimento — v0.2.0

API local em `http://localhost:8000/api`. Swagger em
`http://localhost:8000/api/docs/`; schema em `/api/schema/?format=json`.
O arquivo `docs/openapi.yaml` é gerado pelo drf-spectacular, não editado manualmente.

## Preparação no ambiente existente

Preserve o `.env` e os volumes já configurados. A migration `chat.0001_initial`
adiciona acesso demonstrativo, conversas e turnos; não reimporta a loja.

```sh
docker compose up -d --wait db ollama
docker compose run --rm --no-deps backend python manage.py migrate --noinput
docker compose up -d --wait backend
```

O operador local emite um acesso vinculado ao cliente sintético 1:

```sh
docker compose exec backend python manage.py create_demo_access --customer-id 1 --hours 24
```

O comando imprime `access_id`, `access_token` e `expires_at`. O token é uma
credencial privada de 256 bits e só seu hash é armazenado; não o salve no Git nem
na configuração pública do frontend. O acesso padrão vale 24 horas; máximo 168.
O usuário Django criado não possui senha utilizável. Para revogar:

```sh
docker compose exec backend python manage.py revoke_demo_access ACCESS_ID
```

Somente o comando local escolhe o cliente. Não há seleção pública por ID, e-mail
ou nome. Isso identifica um participante da demonstração; não verifica a identidade
de um cliente real. Emissão e revogação devem ficar sob controle do operador.

## Usar pelo Swagger

1. Execute `GET /api/chat/session/`. Ele retorna `csrf_token` e define o cookie CSRF.
2. Execute `POST /api/chat/session/` com o `access_token` emitido e o token CSRF
   no campo de header `X-CSRFToken`. O navegador recebe o cookie HttpOnly da sessão.
3. O login retorna um **novo** `csrf_token`. O Swagger usa automaticamente o cookie
   atualizado; clientes próprios devem atualizar seu header com o novo valor.
4. Execute `POST /api/chat/conversations/` com `{}` e o novo header CSRF.
5. Copie o `id` da conversa para `conversation_id` nas rotas de mensagens.
6. Envie uma mensagem com `text` e um UUID em `request_id`; consulte o histórico
   pelo GET da mesma rota. Use um novo UUID para cada envio diferente.
7. `DELETE /api/chat/session/`, também com CSRF, encerra o acesso do navegador.

O Swagger normaliza o header CSRF sem diferenciar maiúsculas/minúsculas e lê o
cookie atual a cada envio. Isso evita duplicar o header manual com o automático
ou reutilizar o segredo anterior ao login. Após atualizar o código, recarregue a
página do Swagger para carregar o interceptor corrigido.

O cookie é administrado pelo navegador; não é necessário preencher o botão
Authorize com o token de demonstração. Esse token pertence ao POST de sessão.
Para obter um UUID no terminal:

```sh
docker compose exec backend python -c 'import uuid; print(uuid.uuid4())'
```

Os exemplos da documentação são ilustrativos. As conversas reais de validação
ficam em `docs/validation`; o texto exato pode variar entre gerações.

## Rotas e contratos

| Método | Caminho relativo a `/api` | Comportamento |
| --- | --- | --- |
| GET | `/chat/session/` | Estado anônimo/autenticado, CSRF e validade; sem contatos ou ID do cliente. |
| POST | `/chat/session/` | Troca `access_token` por sessão e escopo de navegador novos. |
| DELETE | `/chat/session/` | Encerra a sessão; não transfere suas conversas a um novo login. |
| GET | `/chat/conversations/` | Lista apenas as conversas desta sessão, 20 por página (`?page=2`). |
| POST | `/chat/conversations/` | Cria conversa; corpo vazio `{}`, cliente obtido da sessão. |
| GET | `/chat/conversations/{id}/messages/` | Histórico cronológico completo, limitado a 25 turnos. |
| POST | `/chat/conversations/{id}/messages/` | Envia texto ao agente e persiste a resposta efetiva. |

As rotas de conversas/mensagens exigem sessão válida. Campos desconhecidos são
rejeitados, inclusive `customer_id`, `owner` e conteúdo de histórico enviado pelo
cliente. Cada turno representa uma mensagem do usuário e uma resposta do agente:

```json
{
  "request_id": "14c832eb-7c36-49aa-98ca-0bf81ee316ea",
  "text": "Quais violões disponíveis até R$ 1000?"
}
```

`text` preserva o texto enviado, deve ter 1–2.000 caracteres e não pode conter só
espaços. O retorno contém `turn` e `replayed`. O turno traz `id`, `request_id`,
`user_message`, `text` da resposta, `status`, `sources`, `tools_used`,
`validation_errors` e `created_at`. Referências de PDF têm arquivo, versão, página
e seção. Não são expostos contatos de clientes, token, estado interno ou ferramentas brutas.

O histórico HTTP é persistido no PostgreSQL. Em cada chamada, uma nova instância
do agente recupera até quatro pares de contexto e até oito referências ID/nome;
preço/estoque precisam ser renovados por ferramenta. O CLI continua com histórico
somente em memória. Falhas aparecem no histórico HTTP, mas não entram no contexto
de geração. O limite é 25 envios por conversa, incluindo falhas.

## Retries, concorrência e erros

| HTTP | Significado |
| --- | --- |
| 200 | Leitura/login ou repetição de um turno já concluído com sucesso. |
| 201 | Conversa criada ou novo turno concluído com sucesso. |
| 204 | Logout concluído. |
| 400 | Corpo/campos inválidos; não chama o agente. |
| 401 | Token demonstrativo inválido, revogado ou expirado no login. |
| 403 | Sem sessão, acesso revogado/expirado ou falha de CSRF/origem. |
| 404 | Conversa ausente ou fora desta sessão: mesma resposta nos dois casos. |
| 409 | Envio em andamento, UUID reutilizado com texto diferente ou limite de 25 turnos. |
| 422 | Turno persistido, mas agente não confirmou a resposta ou atingiu limite interno. |
| 429 | Limite de requisições; respeite `Retry-After`. |
| 503 | Indisponibilidade do modelo/dados ou falha operacional do agente. |

Mesmo `request_id` e mesmo texto na mesma conversa retornam o turno anterior,
sem chamar o modelo novamente. Texto diferente com esse UUID retorna 409. O retry
de uma falha preserva o HTTP 422/503 e traz `replayed=true`; para tentar uma nova
geração, envie outro UUID. Se a primeira chamada ainda estiver em andamento, o
retry recebe 409; aguarde e repita o mesmo UUID.

O PostgreSQL trava somente a linha da conversa com `SELECT FOR UPDATE NOWAIT`.
Turno e estado são gravados juntos. Uma queda antes do commit desfaz ambos; não
há compra ou outra ação externa a repetir. Conversas distintas não compartilham
contexto. A geração é síncrona: são até quatro chamadas de modelo, cada uma com
timeout configurado (120 s no ambiente atual), não 120 s para todo o atendimento.

Erros de contrato/autorização usam o envelope:

```json
{"error":{"code":"validation_error","message":"Revise os campos enviados.","fields":{"customer_id":["Campo não permitido."]}}}
```

Falhas efetivas do agente retornam `turn`/`replayed`, inclusive em 422/503, para
que a interface apresente e recupere a mensagem persistida. Um erro de infraestrutura
que impeça persistir retorna `error` com 503; o schema documenta as duas variantes.
`status=ok` expressa conclusão sob as proteções atuais; não certifica toda frase do LLM.

## Sessão e integração futura com Next.js

Cookie de sessão HttpOnly, proteção CSRF inclusive no login anônimo, revogação
e validade verificadas a cada requisição. Cada login cria um novo identificador
de navegador: dois navegadores com o mesmo token não leem as conversas um do outro.
Recarregar a página mantendo a sessão permite recuperar o histórico; novo login,
logout ou expiração não recuperam automaticamente o escopo anterior.

No frontend, use `fetch` com `credentials: "include"` e envie `X-CSRFToken` em
POST/DELETE. Obtenha o CSRF pelo GET de sessão e atualize-o após o login. O backend
permite credenciais nas origens CORS configuradas; `DJANGO_CSRF_TRUSTED_ORIGINS`
usa essas origens como padrão e pode ser configurado separadamente. O `.env`
existente não precisa ser sobrescrito.

Limites locais: 30 requisições/minuto nas rotas de sessão/conversas e 10/minuto
nas rotas de mensagens, por usuário autenticado ou IP anônimo. O throttle usa o
cache local do processo; não é um limitador distribuído. A transação fica aberta
durante a geração. Antes de um deploy público serão necessárias configuração
HTTPS/cookies para as origens escolhidas e revisão de servidor, limites e timeouts.
O runtime atual é de desenvolvimento, e o frontend de chat ainda não foi implementado.

## Verificar e regenerar

```sh
docker compose run --rm --no-deps -T backend python manage.py test tests --noinput
docker compose run --rm --no-deps -T backend python manage.py spectacular --validate --fail-on-warn > docs/openapi.yaml
docker compose run --rm --no-deps -T backend python manage.py shell < scripts/validate_chat_api.py
```

O último comando exige a fixture sintética e `qwen3:1.7b`. Ele usa HTTP real,
cookies/CSRF, modelo real, retry e isolamento entre navegadores. Cria um usuário,
acesso, sessões e conversa temporários e remove somente esses registros no final,
mesmo em falha. Não emite uma credencial para uso posterior nem imprime seus tokens.

Teste JavaScript do interceptor, com Node.js disponível: `node scripts/test_swagger_csrf.mjs`.
