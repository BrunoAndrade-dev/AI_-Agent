# Integração do material original — 04/11/2026

## Base ativa e preservação

A API local passou a usar `emporio_original`, com `compose.original.yaml` aplicado
sobre o Compose principal. O `.env` e os volumes existentes não foram alterados.
O backend continua em 127.0.0.1:8000; o frontend, em localhost:3000. O cookie
`emporio_original_session` separa o acesso do cookie da base sintética.

Importação original: 9 categorias, 65 produtos, 50 clientes, 20 pedidos, 22 itens,
25 promoções. Manual versão 2.1: oito páginas, 28 trechos. Foram mantidos os
alertas da fonte, incluindo e-mail compartilhado, totais históricos diferentes
do catálogo atual e produtos não ativos com estoque. Nenhum dado foi corrigido
silenciosamente para facilitar a demonstração.

A base sintética foi verificada contra as seis fixtures e o manual. Antes e
depois, manteve cinco produtos, dois clientes, sete conversas e 13 turnos.
O registro agregado está em `synthetic-preserved.json`.

## Problema encontrado com os dados originais

Na primeira consulta de Takamine GD20, o modelo acrescentou o filtro `Guitarras`,
embora o instrumento esteja em `Violões`. A busca retornou zero resultados, sem
inventar um preço. A decisão está em `query-before-fix.json`; a conversa anterior
permanece no banco, fora da seleção final.

As categorias continuam vindo do banco, mas agora o schema permite o filtro
somente quando há uma palavra de categoria reconhecida na mensagem atual.
Perguntas apenas por nome de produto não permitem esse filtro inferido. Isso
evita o caso observado, sem criar um mapeamento fixo de Takamine para uma categoria.
O reconhecimento é lexical, não uma prova geral de compreensão da intenção.

Aliases de categoria foram centralizados para manter busca e schema consistentes.
Dois testes verificam rejeição do filtro inferido e preservação do tipo explícito.

Durante a limpeza inicial, a ordenação de imports acionou o autoreload do Django
e interrompeu um envio em andamento. O histórico foi conferido antes de repetir
o mesmo UUID. Não houve turno duplicado. Os exemplos selecionados foram executados
com o código estabilizado, depois da correção de categoria.

## Regra de PIX com promoção

A primeira resposta desse cenário consultou somente a tabela geral de pagamento
(seção 3) e afirmou incorretamente que o PIX seria aplicado mesmo em promoção.
O status `ok` daquela execução não detectou a contradição. A resposta efetiva e
as fontes estão em `policy-before-fix.json`, como evidência anterior à correção.

Agora uma pergunta explícita sobre PIX e promoção exige busca de cumulatividade.
A resposta usa o trecho atual do manual que contém a regra de promoções/PIX,
sem confiar na interpretação do modelo. Se houver apenas a tabela de pagamentos,
não conclui a regra de promoção. Dois testes cobrem a contradição do modelo e a
falta da evidência necessária. A regra não foi inventada em código: o trecho
correspondente é recuperado do manual indexado e mantém sua proveniência.

## Cenários da demonstração

Os exemplos 01–03 anteriores, sintéticos, foram mantidos. O quarto sintético foi
movido para a validação histórica, e dois exemplos originais completam a seleção
de cinco em `docs/examples/README.md`:

- Catálogo original: Takamine GD20, disponibilidade e continuidade no PIX.
- Manual original: horários de sábado/domingo e regra de PIX em produto promocional.

A exportação confere a base original contra os seis arquivos e o checksum do PDF,
filtra pelo acesso criado nesta avaliação e permite somente as perguntas previstas.
Respostas com contatos dos clientes são recusadas. Não exporta token, cookies,
identificadores de sessão, nomes ou pedidos dos clientes originais.

Resultado final: duas conversas originais, quatro turnos com status `ok`, todos
conferidos contra as fontes. O Takamine GD20 tem cinco unidades, preço de tabela
R$ 2.199,00 e PIX R$ 2.089,05. O manual confirma sábado 09:00–13:00, domingo
fechado e proibição de aplicar o desconto PIX sobre preços promocionais.
A regra foi citada da seção 6.2, página 6, versão 2.1. A sessão e o histórico
foram recuperados após recarregar a página.

`conversations.json` guarda os quatro turnos selecionados. Os textos foram
comparados com os dois arquivos Markdown, sem alteração das respostas. Há cinco
conversas na seleção principal: três sintéticas anteriores e duas originais.
As tentativas descartadas continuam no banco e suas falhas estão documentadas.

## Limpeza e verificações

- Validação de fontes e métricas dos scripts sintéticos centralizadas em
  `backend/tests/evaluation.py`, removendo blocos repetidos.
- Imports locais declarados no Ruff para resultado consistente entre diretórios.
- Exemplo sintético não selecionado arquivado, sem apagar transcrição histórica.
- Captura redundante sem uso (`desktop-reference-size.jpg`) removida; imagens
  de comparação e evidências referenciadas foram preservadas.
- TypeScript com `noUnusedLocals` e `noUnusedParameters`: aprovado, sem código
  morto detectado no frontend.
- 131 testes de backend aprovados em banco de teste separado; cinco testes do
  cliente HTTP aprovados. Os testes automatizados usam doubles para geração.

Instruções de ativação/reversão: `docs/original-demo.md`. O README recebeu somente
ajustes de estado e referências necessários para não apresentar a base errada;
a revisão editorial final fica para a próxima etapa.

O modelo não foi treinado com os arquivos: continua consultando banco e manual por
ferramentas. A latência da inferência local e a limitação semântica geral permanecem.
Não houve commit, push, merge, deploy ou publicação externa.
