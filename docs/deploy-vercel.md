# Demonstração na Vercel

O frontend está em https://emporio-da-musica-ia.vercel.app/. A publicação foi
feita pelo plugin da Vercel, enviando somente os arquivos de `frontend/`, sem
commit, push, conexão Git ou envio do `.env`.

## Arquitetura e dados

O navegador acessa `/api` no próprio domínio. Um rewrite da Vercel encaminha as
requisições a um Cloudflare Quick Tunnel HTTPS, que chega ao serviço Docker
`public_api`. Esse serviço usa Gunicorn, `DEBUG=False`, cookies `Secure`, CSRF
e uma base separada, `emporio_public_demo`. Somente os CSVs e o PDF de
`data/synthetic` foram importados: 5 produtos, 2 clientes e 2 pedidos.

O frontend, o backend local, as bases anteriores, o `.env` e os volumes
existentes continuam disponíveis. PostgreSQL e Ollama não têm endpoints públicos.
Os códigos do ambiente original não autenticam na demonstração pública.

Validação realizada em 04/11/2026: build de produção `READY`, TypeScript e teste
do frontend aprovados; sessão HTTPS retornando 200 e CSRF de 64 caracteres;
cookie `Secure` e `Cache-Control: no-store`; login e criação de conversa pelo
navegador; resposta à pergunta sobre arrependimento com fontes do
`policies-demo.pdf`. Essa verificação não resolve a falha de catálogo relatada
no README nem garante sucesso para todas as perguntas.

O perfil de demonstração usa HSTS de uma hora apenas no próprio host. Os avisos
do `check --deploy` sobre `includeSubDomains` e `preload` são esperados: não se
aplica uma política permanente a subdomínios de um endereço temporário.

## Operação do ambiente preparado

Execute os comandos na raiz do repositório. `.runtime/tunnel.env` contém a imagem
cloudflared fixada por digest; `.runtime/public-demo.env` contém os hosts e as
origens HTTPS exatos. Ambos são locais e ignorados pelo Git.

```bash
# Ver os dois serviços adicionais, sem alterar o ambiente local.
docker compose --env-file .env --env-file .runtime/tunnel.env -f compose.yaml -f compose.demo.yaml ps

# Gerar acesso de 24 horas ao cliente fictício 1.
docker compose --env-file .env --env-file .runtime/tunnel.env -f compose.yaml -f compose.demo.yaml exec public_api python manage.py create_demo_access --customer-id 1 --hours 24

# Consultar o endereço temporário do túnel.
docker compose --env-file .env --env-file .runtime/tunnel.env -f compose.yaml -f compose.demo.yaml logs api_tunnel

# Parar somente a exposição pública; não usar down -v.
docker compose --env-file .env --env-file .runtime/tunnel.env -f compose.yaml -f compose.demo.yaml stop api_tunnel public_api
```

Copie somente `access_token` para o campo de acesso da aplicação. Não publique
esse código no README ou no Git. O acesso expira e pode ser revogado usando
`revoke_demo_access UUID` no mesmo serviço.

## Preparação em outra máquina

1. Suba `db` e `ollama`, baixe o modelo e construa a imagem local do backend como
   descrito no README. Construa a imagem adicional:
   `docker build -f docker/backend/Dockerfile.demo -t emporio-musica-backend:demo .`.
2. Crie a base vazia `emporio_public_demo` com o usuário PostgreSQL configurado.
   Não reutilize as bases original ou sintética de desenvolvimento.
3. Crie `.runtime/tunnel.env` com
   `CLOUDFLARED_IMAGE=cloudflare/cloudflared@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba`.
4. Crie `.runtime/public-demo.env` com `DJANGO_ALLOWED_HOSTS` contendo `localhost`,
   `public_api`, o hostname do túnel e os hostnames da Vercel. Defina
   `DJANGO_CSRF_TRUSTED_ORIGINS` e `DJANGO_CORS_ALLOWED_ORIGINS` com as URLs HTTPS
   exatas da Vercel, separadas por vírgulas. Nunca use curingas.
5. Usando o mesmo prefixo Compose dos comandos acima, execute
   `up -d --no-deps public_api`, seguido de `exec public_api python manage.py migrate`;
   `exec public_api python manage.py import_store_data --directory /data/synthetic`;
   e `exec public_api python manage.py ingest_policies /data/synthetic/policies-demo.pdf --document-version demo`.
6. Inicie `api_tunnel` com `up -d --no-deps api_tunnel`, leia o hostname nos logs,
   atualize os hosts permitidos e recrie somente `public_api`.
7. Na Vercel, use framework Next.js, raiz `frontend`, Node 24, instalação
   `npm ci`, build `npm run build`. Configure `NEXT_PUBLIC_API_BASE_URL=/api` e
   `API_UPSTREAM_ORIGIN=https://HOST-DO-TUNEL` em Production. Faça o deploy pelo
   plugin. O destino do rewrite preserva a barra final exigida pelo Django.
8. Verifique `/api/health/`, sessão, login com CSRF, criação de conversa e resposta
   do modelo pelo domínio da Vercel antes de compartilhar.

## Disponibilidade e limites

Esta é uma demonstração temporária: a máquina precisa permanecer ligada,
conectada e com Docker, API, PostgreSQL, Ollama e túnel funcionando. O endereço
do Quick Tunnel pode mudar ao reiniciar. Nesse caso, atualize os hosts da API e
`API_UPSTREAM_ORIGIN` na Vercel e publique novamente; a variável é usada no build.

Rewrites externos da Vercel têm limite de 120 segundos. Uma resposta lenta,
especialmente com o modelo descarregado, pode atingir esse limite mesmo que a
API continue processando. Aumentar o timeout do Gunicorn não altera esse limite.
O frontend preserva o identificador da requisição para repetir uma tentativa
com segurança. Esse desenho não constitui hospedagem permanente da API nem
garantia de disponibilidade.

Referências: [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
e [limites da Vercel](https://vercel.com/docs/limits).
