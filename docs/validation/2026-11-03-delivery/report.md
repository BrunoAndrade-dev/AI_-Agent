# Preparação da entrega — 03/11/2026

Registro histórico desta rodada. Na seleção de 04/11/2026, o quarto exemplo
sintético foi movido para `not-selected/` e substituído por dois cenários originais.
As quatro transcrições originais desta rodada continuam em `conversations.json`.

## Medição de carregamento e repetição

`measure_agent_latency.py` executou três vezes a mesma pergunta, em instâncias
novas do agente, com o mesmo modelo/base/configuração. O estado inicial de
`/api/ps` não tinha modelos carregados. Não houve descarregamento forçado.

| Consulta | Tempo do turno | Carga reportada pelo Ollama, somada | Chamadas ao modelo |
| --- | --- | --- | --- |
| Primeira, a frio | 136,99 s | 88,515 s | 4 |
| Segunda, carregado | 38,49 s | 0,003 s | 4 |
| Terceira, carregado | 37,54 s | 0,050 s | 4 |

As três retornaram os preços esperados. O cálculo considera o turno inteiro;
`load_duration` vem em nanossegundos e foi convertido para segundos. A primeira
chamada da primeira consulta reportou 88,485 s de carga. As repetições podem se
beneficiar também de cache de prompt; não é um experimento que isola somente RAM.
Três consultas não definem percentis, SLA ou comportamento sob concorrência.

Conclusão: aquecer ajuda, mas não resolve o custo das quatro chamadas e do reparo
de consulta. Não houve aumento de timeout, troca de modelo ou alteração do `.env`.
O procedimento de demonstração está em `docs/frontend.md`. A medição precede a
correção de continuidade PIX abaixo; os dados brutos estão em `latency.jsonl`.

## Regressão encontrada pela interface

A busca inicial por violões funcionou. No seguimento "E no PIX?", o planejador
selecionou `search_products` e depois produziu preços sem suporte na consulta.
As três tentativas de redação foram rejeitadas por `unsupported_price`, resultando
em falha segura HTTP 422. Identidades e histórico existiam; a consulta escolhida
não renovou o produto conhecido. A falha está em `pix-before-fix.json` e permanece
no banco, sem apagar ou reescrever turnos.

Correção: o seguimento curto de PIX exige `get_product` se há exatamente uma
referência conhecida. Com zero ou várias referências, solicita identificação.
A referência guarda somente ID/nome; preço e estoque são consultados novamente.
Dois testes novos verificam preço alterado e contexto ambíguo. Uma nova conversa
foi iniciada depois da correção, com busca e seguimento bem-sucedidos na interface.

Não foi adicionado parser geral de linguagem, escolha arbitrária entre produtos
ou reutilização de preços do histórico. O modelo ainda pode falhar em perguntas
mais amplas; o caso reparado é específico e reproduzível.

## Interface e documentação

As respostas em linhas estavam colapsadas num parágrafo. O CSS de parágrafos do
Markdown agora preserva quebras de linha. O valor computado `white-space:pre-line`
e a captura do catálogo confirmaram a aplicação após recarregar. O texto da API
permanece igual. As fontes documentais puderam ser expandidas, mostrando seção,
página e versão do manual sintético.

O README recebeu instalação completa, indexação do PDF, modelo avaliado, arquitetura,
retrieval, prompt, limitações e ligação para os exemplos. O `design-qa.md` deixou
de depender do caminho temporário da referência e explicita seu escopo visual.

## Evidências e verificação

Foram exportadas quatro conversas, totalizando oito turnos com status `ok`:

| Exemplo | Turnos | Conferência |
| --- | --- | --- |
| Catálogo/PIX | 2 | Nylon disponível, tabela 1.000, promoção/PIX 900, sem acumular desconto |
| Pedidos/privacidade | 3 | Pedido próprio entregue; duas negativas para pedido alheio, inclusive troca de identidade por texto |
| Pedido/devolução | 1 | `get_order` e `search_policies`, confirmação de canal/recebimento, sem aprovação |
| Indisponibilidade/escopo | 2 | Ativo sem estoque versus descontinuado com estoque; resposta de escopo à solicitação de código |

A transcrição completa é preservada em `conversations.json` e nos quatro arquivos
Markdown de `docs/examples/`. O exemplo de devolução tem um único turno com duas
consultas e atende ao cenário não trivial; não demonstra acompanhamento estruturado
de canal/data em vários turnos. `ok` não certifica perguntas arbitrárias.

A exportação conferiu todos os registros das seis tabelas contra os CSVs
sintéticos, além do checksum do PDF. Os textos dos turnos foram comparados com
os arquivos Markdown gerados, sem alteração das respostas. As capturas são trechos
visíveis da interface, não imagens de toda a conversa rolável.

A conversa final foi recuperada após recarregar. No viewport 390 × 844, a largura
de conteúdo observada foi 375 px, sem overflow horizontal, e o estilo de parágrafo
continuou `pre-line`. O viewport temporário foi restaurado ao terminar.

- `tests.txt`: 121 testes de backend aprovados.
- `frontend-tests.txt`: cinco testes do cliente HTTP aprovados.
- Os testes de backend usam PostgreSQL em banco de teste separado; gerações são
  doubles, não evidência de qualidade do modelo real.
- Os exemplos de `docs/examples/` são respostas reais da aplicação pela interface,
  exportadas de `ChatTurn`, com catálogo/manual sintéticos verificados na exportação.
- `export_demo_conversations.py` exige início de rodada com timezone e quatro
  exemplos distintos, sem exportar acesso, cookies ou identificadores de sessão.
- O código parte do commit `854b564`, com alterações locais desta rodada. Os hashes
  relevantes estão em `code-sha256.json`.

Nenhuma configuração privada, volume, conversa anterior ou arquivo original foi
substituído. Os novos exemplos ficam no histórico da sessão existente. Não houve
novo commit, push, deploy ou envio de e-mail.
