# Containers de desenvolvimento

O Compose na raiz reúne Next.js, Django, PostgreSQL e Ollama. Banco e modelo não
publicam portas no host. A API e o frontend são publicados somente em loopback.
Os Dockerfiles são de desenvolvimento e não representam um deploy de produção.

O health check de Django verifica somente liveness. O de Ollama verifica o
servidor, não a presença ou qualidade do modelo. A primeira execução requer
migrations e download explícito de um modelo, conforme README e `ollama/README.md`.

Antes de compartilhar a API por túnel HTTPS, implementar identificação da sessão,
limites de requisições e configuração própria de exposição. Não expor o servidor
de desenvolvimento ou a porta do Ollama como serviço público.

A imagem Ollama usa `latest` provisoriamente. Fixar uma versão/digest após a
validação do runtime. O lockfile Python será definido na etapa de dependências.
