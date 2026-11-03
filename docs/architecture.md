# Arquitetura inicial

## Fluxo

Navegador → Next.js → API Django REST Framework → serviços de domínio.
O backend consulta PostgreSQL, recupera políticas e chama Ollama na rede interna.
Regras financeiras e consultas são executadas por código, não pelo LLM.

## Domínios

- `core`: infraestrutura e contratos compartilhados mínimos.
- `catalog`: categorias, produtos, disponibilidade, promoções e preços.
- `customers`: clientes e limites de acesso.
- `orders`: pedidos e itens, preservando os totais históricos.
- `chat`: sessões, mensagens, ferramentas e integração com o modelo.
- `knowledge`: ingestão do manual e recuperação com página/seção/versão.

Views cuidarão do transporte HTTP, serializers da validação de contratos e
serviços das regras e integrações. Introduzir módulos conforme sua implementação,
sem gerar camadas vazias para cada operação.

## Segurança e dados

Endpoints de negócio exigem autenticação por padrão. O mecanismo de sessão
demonstrativa ainda será implementado, sem listar publicamente os clientes.
Os CSVs originais ficam em `data/private`, fora do Git e das imagens Docker.
Fixtures sintéticas serão fornecidas para reprodução pública.

## Políticas e suposições

- Disponível: status `active` e quantidade maior que zero.
- Promoção: somente `is_active`; não inferir vigência pelo nome da campanha.
- Não acumular promoções com 5% do PIX.
- Totais históricos não são recalculados a partir do catálogo atual.
- Não tratar entrega estimada como data de recebimento.
- Não aprovar devoluções automaticamente sem contexto necessário.
- Contatos divergentes, parcelamento ambíguo e frete em exatamente R$ 500
  exigem explicitação da incerteza e confirmação, sem corrigir fontes silenciosamente.
- Datas de funcionamento usam `America/Campo_Grande`.
- Informações sem fonte e ações não executadas não podem ser apresentadas como fatos.

## Deploy planejado

Next.js na Vercel; backend, PostgreSQL e Ollama na máquina do desenvolvedor.
Um túnel HTTPS exporá apenas a API após os controles de acesso e limites estarem
implementados. A demonstração depende da máquina e do túnel ativos. Vercel não
executará Ollama ou os containers. Teste local completo via Compose é a entrega
reproduzível principal.
