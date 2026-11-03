# Correção CSRF do Swagger — 03/11/2026

O cURL da aba do usuário confirmou dois headers: `X-CSRFToken` (parâmetro manual)
e `X-CSRFTOKEN` (interceptor do drf-spectacular 0.29.0). HTTP trata os nomes sem
sensibilidade a caixa; o navegador pode combinar os valores com vírgula, produzindo
um token de comprimento inválido. O corpo de login não era a causa desse erro.

O interceptor original também embutia o token da renderização da página, que
fica desatualizado após a rotação de segredo no login.

A view Swagger agora preserva o interceptor original para autenticação e usa um
wrapper que remove duplicações, lê o cookie CSRF atual em cada envio e só envia
CSRF para a própria origem em métodos inseguros. Na ausência de cookie, preserva
o token manual. A proteção CSRF do backend continua obrigatória, inclusive no login.

Verificações:
- `node scripts/test_swagger_csrf.mjs`: reproduz a união de headers do bug e testa
  deduplicação, rotação de cookie, manutenção de autenticação, origem externa,
  GET e ausência de cookie/token.
- 111 testes Django aprovados, 2,213 s, sem avisos de schema.
- OpenAPI validado com `--validate --fail-on-warn`.
- HTTP 200 do Swagger e confirmação de que o HTML servido contém o interceptor novo.
- Inspeção da aba real confirmou o cURL duplicado anterior; não reenviei o token
  privado do usuário nem efetuei login em seu nome. O novo POST será feito por ele
  depois de recarregar a página.

Sem alterações em .env, volumes, credenciais ou dados da loja; sem commit/push.
