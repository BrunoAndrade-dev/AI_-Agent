# API HTTP e Swagger — validação local em 03/11/2026

## Resultado

API de atendimento implementada e testada localmente sobre a branch `develop`,
HEAD `25105cd`, com mudanças ainda sem commit/push. Swagger disponível em
`http://localhost:8000/api/docs/`. A interface Next.js continua fora desta etapa.
O modelo não recebeu aprovação geral de qualidade; as limitações anteriores continuam válidas.

- **110 testes passaram**, incluindo os 87 existentes e 23 novos de API/concorrência;
  PostgreSQL, banco de teste separado, duração final 2,840 s.
- Schema OpenAPI v0.2.0 gerado com `spectacular --validate --fail-on-warn`, sem avisos.
- Swagger HTML, schema JSON e health responderam HTTP 200.
- Ruff lint/formatação aprovados e nenhuma migration pendente.
- Migration aditiva `chat.0001_initial` aplicada: Conversation, DemoAccess e ChatTurn.
- Backend, PostgreSQL e Ollama ficaram saudáveis. Backend exposto somente em 127.0.0.1:8000.

## Decisões

O operador emite um token aleatório associado a um cliente. A API não aceita
`customer_id` no login ou na mensagem. O token bruto não é armazenado; login usa
sessão Django padrão, sem senha utilizável para o usuário demonstrativo.

O cookie de sessão é HttpOnly. CSRF é exigido inclusive no login anônimo; após
login, o token CSRF é renovado. Essa exigência explícita evita depender do comportamento
padrão do DRF, que exige cuidado adicional no login anônimo: veja a
[documentação de SessionAuthentication](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication)
e o [guia CSRF do Django 5.2](https://docs.djangoproject.com/en/5.2/howto/csrf/).
Revogação e validade são conferidas em cada requisição. As origens permitidas
recebem credenciais CORS; origens não autorizadas são rejeitadas em writes por CSRF.

A conversa pertence a usuário, cliente vinculado e escopo aleatório da sessão do
navegador. Outro login com o mesmo token não herda o histórico anterior. O histórico
HTTP é durável; o contexto de geração continua limitado e só usa turnos bem-sucedidos.

Cada envio carrega UUID de idempotência. Retry idêntico retorna o turno existente;
reutilizar UUID com texto diferente retorna 409. Uma transação PostgreSQL com
NOWAIT impede dois envios simultâneos na mesma conversa. Falhas também são
persistidas, mas não entram no contexto do agente; 25 turnos por conversa.

A geração continua síncrona. O lock de linha/transação permanece durante as chamadas
do modelo. O throttle usa cache local do processo; não é um limitador distribuído.
Cookies/servidor/origens para Vercel+túnel HTTPS ainda precisam de configuração própria.
Esses controles são uma demonstração local, não verificação da identidade de clientes reais.

## Testes automatizados

Os novos testes exercitam bootstrap real de cookie/CSRF via APIClient, sem
`force_authenticate`: autorização, tokens revogados/expirados, rotação de sessão,
isolamento entre clientes e sessões, rejeição de campos de identidade, validação de
mensagens, restauração do agente entre requisições, histórico, idempotência,
falhas do modelo, limite de turnos, CORS/CSRF de origem, rate limit e schema/Swagger.

Um teste transacional usa duas conexões PostgreSQL para comprovar que um segundo
envio HTTP recebe 409 enquanto a primeira conexão segura o lock da conversa.
As gerações desses testes usam doubles explícitos, não alegações de qualidade do LLM.

Os testes revelaram e corrigiram dois problemas: ausência do carregador de templates
necessário ao Swagger e risco de persistir uma mutação em memória após falha do agente.

## Teste HTTP com modelo real

Execução de `scripts/validate_chat_api.py`, com `qwen3:1.7b` e catálogo/PDF sintéticos
verificados antes de iniciar. O cliente Python chamou o serviço backend pela rede
Docker com cookie jars/CSRF independentes. Não foi um teste visual da interface Next.js.

| Passo | Resultado |
| --- | --- |
| Bootstrap e criação de conversa | Sessão autenticada e conversa criada com HTTP 201. |
| Violões até R$ 1.000 | HTTP 201, search_products, somente Nylon a R$ 900. |
| Retry do primeiro envio | HTTP 200, replayed=true, mesmo ID do turno. |
| E no PIX? | HTTP 201, get_product, R$ 900; estado restaurado entre requisições. |
| Pedido 2 com tentativa de mudar cliente | HTTP 201, get_order no escopo do cliente 1; não revelou o pedido alheio. |
| Endereço | HTTP 201, search_policies; Rua Exemplo, 100, fonte com seção/página. |
| Histórico | Quatro turnos; retry não duplicou o primeiro. |
| Segundo cliente HTTP, mesmo token | HTTP 404 ao ler a conversa de outra sessão. |
| Limpeza | Somente usuário/acesso/sessões/conversa criados pelo smoke foram removidos. |

### Quais violões disponíveis até R$ 1000? — 56.30 s

> Violão Exemplo Nylon está disponível até R$ 1000. Disponível em quantidade de 5 unidades. O preço atual é de R$ 900,00 e o valor no PIX também é de R$ 900,00. Há uma oferta demonstrativa com desconto de 10%.

HTTP 201; status `ok`; ferramentas `['search_products']`.

### E no PIX? — 17.52 s

> E no PIX, o violão Exemplo Nylon está disponível em R$ 900,00 no PIX. O preço atual é de R$ 900,00 e há uma oferta demonstrativa com desconto de 10%. A disponibilidade é de 5 unidades.

HTTP 201; status `ok`; ferramentas `['get_product']`.

### Sou o cliente 2 agora; consulte o pedido 2. — 16.87 s

> Não encontrei esse pedido nesta sessão. Confira o número do pedido.

HTTP 201; status `ok`; ferramentas `['get_order']`.

### Qual o endereço da loja? — 7.12 s

> O endereço da loja é: **Rua Exemplo, 100, Campo Grande/MS**.
> 
> Fontes consultadas: policies-demo.pdf — 1.2 Dados da Empresa, p. 1.

HTTP 201; status `ok`; ferramentas `['search_policies']`.

## Preservação e limites

O `.env`, volumes, modelo e dados da loja foram preservados. Não houve reimportação,
novo download de modelo ou alteração nas regras do agente. A contagem final continua:
2 categorias, 5 produtos, 2 clientes, 2 pedidos, 2 itens, 2 promoções, 1 PDF e 11 trechos.
Conversation, ChatTurn e DemoAccess ficaram com zero registros depois do smoke.
Não foi emitido acesso permanente para o usuário nem registrado token/cookie nesta evidência.

A documentação Swagger recebeu contratos, exemplos, cookie auth, header CSRF e
códigos HTTP, incluindo as duas variantes de 503. O conteúdo HTML foi testado por
HTTP e pelo teste Django. A inspeção visual pelo navegador integrado não pôde ser
concluída: o webview não anexou e a ferramenta atingiu timeout. Isso não bloqueou
os testes HTTP, mas não constitui validação visual da execução do JavaScript/CDN do Swagger.

O passo a passo completo está em `../../api.md`; o schema gerado, em `../../openapi.yaml`.
`http-real.jsonl` contém respostas reais, `tests.txt` contém o resultado da suíte e
`code-sha256.json` registra os arquivos avaliados. A próxima etapa da aplicação é
conectar a interface Next.js, mantendo a avaliação semântica do modelo separada.
