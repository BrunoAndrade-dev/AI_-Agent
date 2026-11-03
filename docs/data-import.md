# Modelagem e importação de dados

## Modelos

Category → Product → Promotion. Customer → Order → OrderItem → Product.
IDs das tabelas de origem são preservados como chaves primárias inteiras. Itens
recebem ID interno e unicidade pelo par (pedido, produto). Relacionamentos usam
`PROTECT` para impedir exclusões acidentais de registros referenciados.

Valores monetários usam Decimal com duas casas, não float. O importador rejeita
precisão excedente em vez de arredondar silenciosamente. `specs` é JSON por
categoria: o campo `strings` pode representar material ou número de cordas.
Nenhum preço histórico unitário, canal ou recebimento real é fabricado.

O e-mail do cliente não é único. Contatos não autenticam clientes e não serão
expostos em listagens públicas. A camada de acesso será implementada depois.

## Comandos

Coloque os seis CSVs originais em `data/private` e execute a partir da raiz:

```sh
docker compose up -d db
docker compose run --rm --no-deps backend python manage.py migrate
docker compose run --rm --no-deps backend python manage.py import_store_data --directory /data/private --dry-run
docker compose run --rm --no-deps backend python manage.py import_store_data --directory /data/private
```

O banco deve estar saudável antes dos comandos com `--no-deps`. Use
`docker compose ps db` para verificar. Esses comandos pressupõem imagem de backend
já construída com `docker compose build backend` e `.env` preenchido.
Ollama e frontend não são necessários para migrations e importação.

Para dados públicos, substitua `/data/private` por `/data/synthetic`, usando um
banco separado e vazio. Para execução Python fora do Docker, configure as
variáveis do `.env` no processo; Django não carrega o arquivo automaticamente.
O host do PostgreSQL fora do Compose precisa ser ajustado explicitamente.

## Contrato dos arquivos

São obrigatórios `categories.csv`, `products.csv`, `customers.csv`, `orders.csv`,
`order_items.csv` e `promotions.csv`. Também são aceitos os nomes originais com o
prefixo `desafio_tecnico_ai_eng - `. Se ambos os nomes de uma tabela existirem,
o comando rejeita a ambiguidade. UTF-8 com ou sem BOM, delimitador vírgula.

O cabeçalho deve corresponder ao schema esperado, sem colunas ausentes,
duplicadas ou extras. Arquivos vazios são rejeitados. Todos os vínculos devem
existir no mesmo conjunto de entrada, mesmo que o banco já contenha registros.
Cada pedido precisa ter itens. Chaves repetidas são rejeitadas, não mescladas.

Campos vazios de rastreamento e previsão tornam-se NULL; observações vazias
permanecem texto vazio. Datas ISO, JSON objeto, inteiros, limites decimais,
status, pagamentos e indicador de atividade são validados antes da escrita.

## Transação e reimportação

O conjunto completo é gravado em uma única transação. Qualquer falha desfaz toda
a operação. `--dry-run` executa a escrita e as constraints reais e então desfaz
a transação; não é somente uma leitura dos arquivos.

Reexecutar com as mesmas chaves atualiza os registros sem duplicá-los. O relatório
`existing` significa registros encontrados e atualizados, inclusive se os valores
forem idênticos. Registros ausentes nos arquivos não são apagados. Portanto, a
operação é um upsert completo de entrada, não uma sincronização destrutiva. Se
um item mudar de produto, o item anterior permanece: remoções exigirão um fluxo
explícito futuro. Não importar simultaneamente múltiplos conjuntos no mesmo banco.

Uma promoção ativa por produto é a suposição adotada para evitar seleção
arbitrária de descontos não cumulativos. Múltiplas campanhas ativas no arquivo
são rejeitadas. Uma campanha antiga omitida da entrada não é desativada: conflitos
com ela provocam rollback. Para trocar de campanha, inclua a antiga inativa e a
nova ativa. Isso é verificado por constraint parcial no PostgreSQL.

## Alertas que não alteram a fonte

O comando reporta quantidades agregadas de e-mails compartilhados, produtos
não ativos com estoque e divergências entre totais históricos e catálogo atual.
Esses achados não justificam mudar valores originais. Mensagens de erro mostram
tabela, linha e campo, sem contatos ou conteúdo completo de registros.

Na base original: 9 categorias, 65 produtos, 50 clientes, 20 pedidos, 22 itens,
25 promoções; 1 grupo de e-mail compartilhado, 2 totais históricos divergentes
e 2 produtos não ativos com estoque positivo.

O PDF não é ingerido por este comando. Sua recuperação pertence à próxima etapa.

## Validação realizada nesta etapa

- PostgreSQL 17 real, com migrations aplicadas em banco vazio.
- Build da imagem do backend a partir das dependências fixadas.
- Importação original pelo Compose: 191 registros nas seis tabelas.
- Reimportação sem criação de duplicatas e dry-run com rollback.
- `manage.py check` sem problemas e nenhuma migration pendente.
- 20 testes aprovados, também executados dentro do container com PostgreSQL.
- Testes de rollback de criação e atualização após falha, integridade no banco,
  disponibilidade, validação de arquivos e proteção de dados em mensagens de erro.
- Ruff 0.14.3: lint e formatação aprovados.

Para verificar o estilo fora do container, instale `backend/requirements-dev.txt`
em um ambiente virtual e execute, da raiz:

```sh
ruff check backend
ruff format --check backend
```

Esses resultados validam a camada de dados. Não comprovam o funcionamento do
agente, do frontend ou do modelo Ollama, que pertencem às etapas seguintes.
