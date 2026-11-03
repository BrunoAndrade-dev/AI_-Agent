# Dados demonstrativos

Contém seis CSVs inteiramente sintéticos, sem contatos originais: 2 categorias,
5 produtos, 2 clientes, 2 pedidos, 2 itens e 2 promoções. Os contatos usam domínio
reservado `.invalid` e telefones de demonstração.

Os cenários incluem estoque zero, descontinuação com estoque, produto em breve,
promoção ativa e inativa, e-mail compartilhado e total histórico diferente do
catálogo. Servem de base para testes e para reprodução pública do protótipo.

Importe em banco vazio com `import_store_data --directory /data/synthetic` dentro
do container. Não misture com os originais: os IDs podem coincidir.

`policies-demo.pdf` contém duas páginas de políticas sintéticas, com endereço e
contato de demonstração. Não é uma cópia do manual original. Para indexá-lo:

```sh
python manage.py ingest_policies /data/synthetic/policies-demo.pdf --document-version demo
```

Execute dentro do backend, após as migrations. O PDF usa texto extraível sem OCR
e permite testar o mesmo pipeline do manual original sem publicar esse arquivo.
