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
validação do runtime. As dependências Python são fixadas em
`backend/requirements.lock.txt`.

Em ambientes com proxy TLS corporativo, o Dockerfile do backend aceita o segredo
BuildKit opcional `proxy_ca`, apontando para um bundle confiável de certificados.
Ele é usado apenas durante a instalação, sem persistir na imagem. Não desabilitar
a validação TLS. O desenvolvimento local sem proxy dispensa esse segredo.
