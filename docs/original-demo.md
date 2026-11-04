# Demonstração com o material fornecido

As duas bases são independentes, no mesmo PostgreSQL local:

| Modo | Configuração | Dados |
| --- | --- | --- |
| Sintético | `compose.yaml` | Fixtures públicas e manual de demonstração |
| Original | `compose.yaml` + `compose.original.yaml` | Seis CSVs fornecidos e manual versão 2.1 |

O modo original usa o banco `emporio_original` e um cookie de sessão próprio.
Ele não importa os originais sobre os IDs sintéticos. `.env`, volume PostgreSQL,
volume do Ollama e sessões da base sintética são preservados.

## Preparação inicial

Coloque os originais em `data/private` com os nomes `categories.csv`,
`products.csv`, `customers.csv`, `orders.csv`, `order_items.csv`, `promotions.csv`
e `policies.pdf`. Os CSVs também aceitam o prefixo original do desafio; mantenha
apenas uma das convenções, evitando duplicação de nomes. Esses arquivos ficam
fora do Git e das imagens Docker.

Com PostgreSQL e o backend local ativos:

```sh
docker compose exec backend python manage.py create_original_database
docker compose -f compose.yaml -f compose.original.yaml run --rm --no-deps backend python manage.py migrate
docker compose -f compose.yaml -f compose.original.yaml run --rm --no-deps backend python manage.py import_store_data --directory /data/private
docker compose -f compose.yaml -f compose.original.yaml run --rm --no-deps backend python manage.py ingest_policies /data/private/policies.pdf --document-version 2.1
docker compose -f compose.yaml -f compose.original.yaml up -d
```

O comando de criação não apaga nem sobrescreve um banco existente. A importação
valida e atualiza os registros pelos IDs; use esse procedimento somente na base
original. A instalação já realizada contém 9 categorias, 65 produtos, 50 clientes,
20 pedidos, 22 itens, 25 promoções e 28 trechos do manual de oito páginas.

## Usar e reiniciar

```sh
docker compose -f compose.yaml -f compose.original.yaml up -d
docker compose -f compose.yaml -f compose.original.yaml exec backend python manage.py create_demo_access --customer-id 1 --hours 24
```

Abra [http://localhost:3000](http://localhost:3000) e use apenas o `access_token`
retornado. O token é privado. A identidade continua definida pelo operador; não
é possível trocar de cliente por uma mensagem. Os exemplos públicos novos consultam
somente catálogo e políticas, sem dados pessoais ou pedidos dos clientes originais.

Perguntas dos dois novos cenários:

- "Quanto custa o Takamine GD20? Ele está disponível?", seguida de "E no PIX?".
- "Qual o horário de funcionamento aos sábados e aos domingos?", seguida de
  "Qual é a regra do PIX quando o produto já está em promoção?".

Para voltar à base sintética:

```sh
docker compose -f compose.yaml up -d
```

Recarregue a página após alternar. O backend usa a mesma porta 8000 nos dois modos,
um modo por vez; a interface não combina fontes. O arquivo adicional deve ser
informado novamente ao iniciar o modo original. Não é necessário alterar o `.env`.

## Seleção para entrega

O índice em `docs/examples/README.md` seleciona cinco conversas: três com fixtures
sintéticas e duas com material original. O quarto exemplo sintético da rodada
anterior permanece como evidência em `docs/validation/2026-11-03-delivery/not-selected/`.
Não foi apagado do histórico. O modelo continua sujeito à latência de CPU e às
limitações documentadas; a base original não implica treinamento ou fine-tuning.
