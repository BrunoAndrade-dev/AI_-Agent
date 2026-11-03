# Ferramentas, políticas e modelo local

## Estado de validação

Consultas, índice do PDF e loop de ferramentas implementados. Testes de protocolo
usam doubles explícitos do modelo. Qualidade das respostas reais, latência e
hardware mínimo **ainda não foram validados**. Houve bloqueios de rede no download
de `qwen3:4b` e, após a liberação dos destinos, quedas do ambiente na nuvem durante
novas tentativas. A validação será retomada na máquina do desenvolvedor com Docker.
Não há fallback de respostas fictícias.

O servidor Ollama 0.40.13 responde a `/api/version` e `/api/tags` na rede interna.
A imagem está fixada por digest, com cloud desativado. Healthcheck não comprova
presença do modelo. API pública de chat e sessão web pertencem à próxima etapa.

Validações realizadas: 60 testes aprovados no backend Docker com PostgreSQL,
incluindo parsing real do PDF sintético; seis verificações de retrieval no manual
original; lint e formatação aprovados; nenhuma migration pendente. Os testes do
loop com doubles não demonstram qualidade de geração ou resistência real do LLM.

## Arquitetura e escolhas

O modelo escolhe ferramentas com schemas JSON estritos. Consultas usam ORM, sem
SQL ou comandos gerados. Preços usam Decimal e arredondamento comercial.

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

`qwen3:4b` é candidato por suportar ferramentas e execução local. Não foi ainda
aprovado por qualidade ou hardware. A avaliação real deve medir português,
seleção de ferramentas, aplicação das políticas, instruções adversas e latência.

```sh
docker compose up -d --wait db ollama
docker compose exec -e OLLAMA_HOST=http://127.0.0.1:11434 ollama ollama pull qwen3:4b
docker compose run --rm --no-deps backend python manage.py chat_store --check-model
```

Loopback explícito no CLI evita encaminhar `0.0.0.0` ao proxy. Não desabilitar
TLS. Configure `OLLAMA_MODEL` e `OLLAMA_TIMEOUT_SECONDS` no `.env`. O Compose
fixa `OLLAMA_BASE_URL` na rede interna. Não usar modelos `:cloud`.
O timeout padrão é 120 segundos por chamada, não por conversa inteira.

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
