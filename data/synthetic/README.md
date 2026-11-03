# Dados demonstrativos

Contém seis CSVs inteiramente sintéticos, sem contatos originais: 2 categorias,
5 produtos, 2 clientes, 2 pedidos, 2 itens e 2 promoções. Os contatos usam domínio
reservado `.invalid` e telefones de demonstração.

Os cenários incluem estoque zero, descontinuação com estoque, produto em breve,
promoção ativa e inativa, e-mail compartilhado e total histórico diferente do
catálogo. Servem de base para testes e para reprodução pública do protótipo.

Importe em banco vazio com `import_store_data --directory /data/synthetic` dentro
do container. Não misture com os originais: os IDs podem coincidir.
