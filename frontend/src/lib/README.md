# Integração com a API

Clientes HTTP e contratos TypeScript serão centralizados aqui. A interface não
acessa PostgreSQL ou Ollama diretamente. Nunca colocar segredos em variáveis
`NEXT_PUBLIC_*`, pois seus valores são enviados ao navegador.
