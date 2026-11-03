# Ferramentas, políticas e modelo local

## Estado de validação

Em 03/11/2026, a validação inicial com `qwen3:1.7b` e a base sintética
**reprovou a configuração anterior para atendimento**: dez turnos naturais sem
ferramentas, incluindo preços e endereço inventados. Uma instrução explícita
conseguiu executar busca real, mas a continuidade não renovou as consultas.
Os 60 testes automatizados passaram novamente. Evidências, tempos e transcrições:
[relatório local](validation/2026-11-03-qwen3-1.7b/report.md).
O `.env` e os volumes foram preservados; o modelo padrão versionado não mudou.

As correções posteriores separam decisão estruturada e redação, validam filtros
contra o catálogo/contexto e rejeitam respostas factuais sem consulta válida.
Foram aprovados 87 testes automatizados. Rodadas reais, falhas remanescentes e
limites estão no [relatório de correções](validation/2026-11-03-agent-corrections/report.md).
O modelo ainda exige revisão de qualidade; esses testes não o aprovam para produção.

O servidor Ollama 0.40.13 responde a `/api/version` e `/api/tags` na rede interna.
A imagem está fixada por digest, com cloud desativado. Healthcheck não comprova
presença do modelo. A API local de chat e sessão demonstrativa está implementada;
veja [contratos HTTP](api.md). A suíte com a API possui 111 testes, além da
[validação HTTP real](validation/2026-11-03-chat-api/report.md). Interface e deploy público
continuam pendentes.

Validações anteriores: 60 testes aprovados no backend Docker com PostgreSQL,
incluindo parsing real do PDF sintético; seis verificações de retrieval no manual
original; lint e formatação aprovados; nenhuma migration pendente. Os testes do
loop com doubles não demonstram qualidade de geração ou resistência real do LLM.

## Arquitetura e escolhas

Cada turno começa com uma decisão do modelo restringida por JSON Schema no
campo `format` do Ollama: nome/argumentos de uma ferramenta ou uma intenção simples
de saudação, esclarecimento ou fora de escopo. Essas intenções usam textos fixos,
sem alegações operacionais. Não há fallback que simule uma consulta bem-sucedida.

As categorias permitidas vêm do banco. `max_price` só admite números presentes
nas mensagens do cliente, nunca valores inventados pelo assistente. Isso limita
defaults alucinados, mas não prova que cada número representa um orçamento. Valores
por extenso podem exigir esclarecimento. Schemas continuam validados pelo Python,
inclusive nas chamadas nativas adicionais após uma consulta. `get_product` só
aceita IDs explicitamente citados pelo cliente ou retornados em consultas anteriores.
A sessão mantém até oito referências ID/nome, sem guardar preços ou estoque antigos.

O modelo redige após receber os dados e pode pedir consultas adicionais pelo
protocolo nativo. Consultas usam ORM, sem SQL gerado. Preços usam Decimal e
arredondamento comercial. Uma verificação parcial bloqueia valores explicitamente
marcados com R$ que não estejam nos preços/trechos consultados. Ela não verifica
toda a semântica nem a associação de um preço ao produto ou meio de pagamento.

Sem evidência válida no turno, a prosa factual é rejeitada; chamadas com erro não
contam como evidência. Há até quatro rodadas/oito chamadas, incluindo correções.
Falha de confirmação retorna `unverified_response`, sem salvar o texto rejeitado
no histórico. `validation_errors` registra rejeições; `tools_used` preserva tentativas
mesmo em falhas. Negativas de pedido são formuladas pelo código, sem confirmar
existência fora da sessão. Resumos exclusivamente de pedidos são formatados a partir
do snapshot, sem transformar estimativa em recebimento real. Perguntas explícitas
sobre devolução/arrependimento exigem política e recebem os trechos do manual mais
uma confirmação de canal e recebimento; não há cálculo de elegibilidade nem aprovação.
Referências do PDF são anexadas ao texto pelo backend.

Para oito páginas, busca lexical com acentos normalizados, sinônimos explícitos,
ranking do tipo BM25 e peso de seção evita outro modelo e infraestrutura vetorial.
Consultas de contato priorizam a seção de dados da empresa porque o capítulo de
privacidade também menciona endereço. Isso não resolve os contatos conflitantes:
a resposta deve reconhecer a divergência, sem escolher silenciosamente.

Seis perguntas reais recuperaram as seções corretas: endereço, sábado,
arrependimento, PIX com promoção, garantia e frete. O índice original possui
28 trechos com página, seção, versão e checksum. Reformulações sem vocabulário
equivalente podem exigir novos sinônimos ou evolução do retrieval.

## Ferramentas

| Ferramenta | Responsabilidade |
| --- | --- |
| `search_products` | Nome/categoria, orçamento, disponibilidade e limite de resultados |
| `get_product` | Status, estoque, especificações e preços de um produto |
| `get_order` | Pedido exclusivamente no escopo do cliente identificado |
| `search_policies` | Trechos do manual com página, seção e versão |

`current_price` considera promoção ativa. `pix_price` usa promoção OU desconto de
5% sobre tabela, nunca os dois. O orçamento filtra `current_price`, sem presumir
PIX. A busca ordena por preço atual e informa total e truncamento.

`get_order` não aceita `customer_id` do modelo. O chamador confiável define
`AgentContext`. Pedido ausente e pedido de outro cliente têm a mesma resposta.
Contatos pessoais não são retornados. Selecionar cliente pelo CLI é facilidade
do operador local, não autenticação; a futura API precisa usar a sessão.

## Índice de políticas

Com banco migrado e backend construído:

```sh
docker compose run --rm --no-deps backend python manage.py ingest_policies /data/private/policies.pdf --document-version 2.1
```

Coloque o original em `data/private`, ajustando o caminho se usar outro nome.
Para demonstração em banco separado, use os CSVs e o PDF sintéticos públicos:

```sh
docker compose run --rm --no-deps backend python manage.py ingest_policies /data/synthetic/policies-demo.pdf --document-version demo
```

O PDF de demonstração é uma fixture identificada como sintética, não o manual
original. O original permanece fora do Git e das imagens.

O índice é substituído atomicamente. Mesmo checksum/versão é ignorado; use
`--rebuild` após alterar a segmentação. Não há OCR. Limites: 10 MiB, 100 páginas,
trechos de aproximadamente 1.500 caracteres, com cortes por palavras. Caminhos
locais não são enviados ao modelo, somente nomes e metadados da fonte.

## Modelo e configuração

As rodadas locais usam `qwen3:1.7b`, configurado no `.env` do desenvolvedor.
O `.env.example` ainda contém o candidato anterior `qwen3:4b`; nenhum modelo foi
aprovado definitivamente. Para reproduzir a avaliação abaixo, configure explicitamente
`OLLAMA_MODEL=qwen3:1.7b` no ambiente local. Não é necessário baixar outro modelo.

```sh
docker compose up -d --wait db ollama
docker compose exec -e OLLAMA_HOST=http://127.0.0.1:11434 ollama ollama list
docker compose run --rm --no-deps backend python manage.py chat_store --check-model
```

Loopback explícito no CLI evita encaminhar `0.0.0.0` ao proxy. Não desabilitar
TLS. Configure `OLLAMA_MODEL` e `OLLAMA_TIMEOUT_SECONDS` no `.env`. O Compose
fixa `OLLAMA_BASE_URL` na rede interna. Não usar modelos `:cloud`.
O timeout padrão é 120 segundos por chamada, não por conversa inteira.
Se o modelo realmente faltar, seu download deve ser uma etapa explícita.

Em redes restritas, o download utiliza `registry.ollama.ai`, `registry.ollama.com`
e o armazenamento de blobs indicado pelo registro. Neste ambiente, foi observado
`dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com`. Os três destinos foram
liberados, mas quedas da máquina impediram confirmar a conclusão do download.
O destino de blobs pode mudar; liberar somente destinos efetivamente observados.

## Conversa pelo terminal

```sh
docker compose run --rm --no-deps backend python manage.py chat_store --message "Quais violões disponíveis até R$ 1000?"
docker compose run --rm --no-deps backend python manage.py chat_store --customer-id 1
```

`/sair` encerra a conversa. Há até quatro pares usuário/assistente em memória,
sem persistência entre processos. Erros não entram no histórico e resultados de
tools são descartados após o turno; o prompt exige renovar consultas operacionais.

Limites: 2.000 caracteres de entrada, quatro rodadas, oito chamadas de tools e
limites adicionais de histórico/contexto. O adaptador aceita somente origem
HTTP interna, não segue redirects e limita respostas a 1 MiB. Falhas de banco
ou modelo têm respostas explícitas sem detalhes internos.

## Segurança e limitações

Schemas e escopo de cliente são impostos por código. Persona, fidelidade da
resposta, recusa de fora de escopo e resistência a prompt injection também
dependem do modelo: o prompt não é garantia. Ainda não há validador semântico
para cada frase gerada. A avaliação real permanece obrigatória.

Textos recuperados são tratados como dados. O agente não possui ferramentas para
comprar, pagar, devolver, cancelar ou registrar reclamação. Lacunas e conflitos
exigem esclarecimento. Antes do túnel público, implementar sessão, limites de
requisição e servidor apropriado. Não expor banco, Ollama ou CLI ao navegador.

## Reproduzir a regressão com o modelo real

Com `qwen3:1.7b`, banco sintético já preparado e PDF sintético indexado:

```sh
docker compose run --rm --no-deps -T backend python manage.py shell < scripts/validate_agent.py
```

O script verifica modelo, IDs/nomes do catálogo sintético e checksum do manual
antes de executar sete cenários/dez turnos. Não importa dados nem modifica a loja.
Cada linha JSON registra pergunta, resposta efetiva, status, ferramentas, rejeições,
mensagens brutas do modelo e duração. O Django pode imprimir um cabeçalho antes do JSON.
As mensagens brutas podem conter respostas rejeitadas; não são o texto entregue ao cliente.
Isso é uma avaliação conhecida e pequena, não uma prova de qualidade geral do modelo.
