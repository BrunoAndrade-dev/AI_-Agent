# Avaliação complementar — 03/11/2026

## Resultado e limites

119 testes automatizados aprovados; lint e formatação aprovados. O agente recebeu
correções de consultas e apresentação de fatos. Isso não aprova atendimento geral:
a inferência local continua lenta, e o conjunto avaliado é pequeno.

## Diagnóstico e correções

- O reconhecimento de IDs só aceitava o singular. Agora aceita listas explícitas
  como "produtos 2 e 3", sem transformar orçamento ou número de pedido em produto.
- Uma busca genérica não comprova o status de cada ID. A resposta exige consultas
  individuais; faltando consulta, retorna ao planejamento estruturado com a
  ferramenta pendente. Nessa reparação, o schema não permite substituir a consulta
  por uma resposta de esclarecimento.
- Resultados exclusivamente de catálogo recebem apresentação determinística:
  preço original, atual, percentual sobre tabela e PIX sem acumular descontos;
  status e estoque são separados. O modelo continua escolhendo as consultas.
  Esta apresentação substitui a redação do LLM, não representa melhora espontânea
  da sua capacidade semântica.
- Perguntas mistas de status de pedido e devolução exigem ambas as fontes e
  preservam as duas partes da resposta. Uma pergunta apenas de devolução não
  força consulta ao pedido quando ele é mencionado somente como contexto.
- Orçamento no formato "até ... reais" por extenso solicita confirmação numérica.
  Não há parser geral de números por extenso.
- A orientação de trocas/devoluções inclui os trechos recuperados de defeito e
  arrependimento, sem aprovar a operação.

O carregamento medido na primeira chamada consumiu 79,02 s; o turno completo de
políticas levou 133,63 s, em duas chamadas menores que o timeout individual de
120 s. Com modelo carregado, a repetição levou 39,78 s. Isso não é benchmark
controlado nem prova retrospectiva da causa do timeout visto no navegador.
Na máquina também foram observados swap quase cheia e 45–46% de espera de disco;
pressão de recursos é um possível contribuinte. Nenhum timeout, modelo, `.env`
ou volume foi alterado para esconder o problema. Não há garantia de latência.

## Dados sintéticos: avaliação real

Sete turnos foram revisados: políticas, promoção, comparação de dois IDs,
orçamento por extenso, pedido com devolução, produto inexistente e solicitação
de executar pagamento. Todos terminaram com resposta segura nos registros
selecionados. O esclarecimento numérico foi determinístico, sem chamar o LLM.
Isso não certifica todas as frases ou perguntas possíveis.

Pedido com devolução passou a consultar ambas as ferramentas e responder às duas
partes (49,94 s), após a execução anterior falhar por falta de política (96,12 s).
Os IDs passaram a distinguir ativo sem estoque de descontinuado com estoque,
após consultar ambos individualmente (62,04 s).

`baseline.jsonl` registra a versão anterior. `iteration-1.jsonl` preserva uma
rodada intermediária, incluindo falha de protocolo durante o desenvolvimento.
`final-ids.jsonl` contém a repetição corrigida dos IDs.
`reviewed-synthetic.jsonl` reúne sete registros revisados dessas execuções;
não é uma única conversa nem uma execução contínua. As mensagens não foram
reescritas para parecerem bem-sucedidas.

## Arquivos originais

Os seis CSVs foram copiados para `data/private`, ignorado pelo Git. A validação
estrita de tipos, chaves, relacionamentos e regras de importação passou:
9 categorias, 65 produtos, 50 clientes, 20 pedidos, 22 itens e 25 promoções.
O manual possui oito páginas e produziu 28 trechos.

Foram preservadas as características da fonte: um grupo de e-mail compartilhado,
dois totais históricos diferentes do catálogo atual e dois produtos não ativos
com estoque positivo. Não houve fusão de clientes nem recálculo dos pedidos.

A importação e os testes ocorreram em bancos temporários com nomes únicos,
criados pelo mecanismo de testes do Django e removidos ao terminar. O catálogo
demonstrativo foi comparado antes/depois e permaneceu igual. O frontend continua
usando os dados sintéticos; não houve troca silenciosa da base de demonstração.

As buscas originais recuperaram seções esperadas de endereço, sábado, pagamento
com promoção, garantia e frete. As execuções reais confirmaram consultas de
produtos não ativos, pedido próprio, bloqueio do pedido de outro cliente e
políticas. A primeira consulta de promoção falhou de forma segura: o planejador
pedia esclarecimento mesmo com um ID conhecido. Isso motivou a restrição do schema
na reparação. A repetição final é registrada separadamente.

**A repetição final da promoção passou**: foram consultadas `search_products` e
`get_product`, e preço de tabela, promocional e PIX conferiram com a fonte. Levou
126,62 s, incluindo novo carregamento frio do modelo. Os seis casos originais
selecionados têm resposta segura nas execuções revisadas (cinco na rodada inicial
e a promoção na repetição), com bancos temporários removidos e catálogo da
demonstração preservado em ambas. O resumo sem dados privados está em
`original-summary.json`; a falha inicial continua registrada.

Isso encerra esta rodada de correção e validação, mas a latência de carregamento
frio permanece uma limitação para demonstração. Não foi comprovada qualidade
geral, resistência ampla a injeções ou bom desempenho em outro hardware.

Respostas e trechos dos originais ficam somente em `.runtime/`, ignorado pelo Git.
Os contatos dos clientes não apareceram nas seis respostas da rodada inicial.
O resumo público contém apenas resultados agregados, sem transcrições privadas.

## Reprodução e preservação

`scripts/evaluate_agent_followup.py`: exige o catálogo/manual sintéticos e
`qwen3:1.7b`, coleta tempos e métricas do Ollama, sem escrever na loja.
`scripts/evaluate_original_data.py`: valida/importa originais em banco temporário;
redirecionar sua saída para local privado. `EMPORIO_EVAL_DATA_ONLY=1` omite geração;
`EMPORIO_EVAL_SCENARIOS=promotion` seleciona somente a repetição da promoção.

Os testes automatizados usam doubles explícitos, não o modelo real. A suíte final
está em `tests-final.txt`; sete regressões anteriores à última restrição de schema
também estão em `tests-targeted.txt`. Nenhum commit/push foi criado. As alterações
locais do frontend, sessões existentes, arquivos originais, `.env` e volumes foram
preservados.
