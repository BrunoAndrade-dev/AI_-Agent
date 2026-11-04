# Integração com a API

`api.ts` centraliza contratos, cookies, CSRF e transporte HTTP.
`use-store-chat.ts` coordena sessão, histórico, envios e recuperação de falhas.
A interface não
acessa PostgreSQL ou Ollama diretamente. Nunca colocar segredos em variáveis
`NEXT_PUBLIC_*`, pois seus valores são enviados ao navegador.
