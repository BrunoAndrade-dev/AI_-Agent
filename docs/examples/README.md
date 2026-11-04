# Conversas selecionadas para a demonstração

Cinco conversas executadas pela interface Next.js → API Django → Ollama local
(`qwen3:1.7b`). São três exemplos com fixtures sintéticas e dois com o material
fornecido no desafio. As perguntas foram escolhidas para avaliação; as respostas
são transcrições reais dos turnos persistidos, sem reescrita para corrigir falhas.
As capturas mostram trechos visíveis; o Markdown preserva a conversa completa.

| Conversa | Material | Capacidade avaliada |
| --- | --- | --- |
| [Catálogo e PIX](01-catalogo-e-pix.md) | Sintético | Orçamento e continuidade com renovação de preço |
| [Pedidos e privacidade](02-pedidos-e-privacidade.md) | Sintético | Pedido próprio, pedido alheio e tentativa de trocar identidade |
| [Devolução e políticas](03-devolucao-e-politicas.md) | Sintético | Consulta de pedido e manual, sem aprovação automática |
| [Takamine GD20](04-catalogo-original.md) | CSVs fornecidos | Produto, estoque, preço e valor no PIX |
| [Horários e pagamento](05-politicas-originais.md) | Manual fornecido, v2.1 | Horários e não cumulatividade de PIX/promoção, com fontes |

## Bases e rastreabilidade

As bases são separadas: os exemplos 01–03 usam cinco produtos, dois clientes,
dois pedidos e `policies-demo.pdf`. Os exemplos 04–05 usam o catálogo original
com 65 produtos e o manual original de oito páginas. A cópia local do manual
é chamada `policies.pdf`, com os mesmos bytes de `políticas_da_loja.pdf`.
Veja [como executar o modo original](../original-demo.md).

Os novos exemplos originais consultam somente catálogo e políticas; não publicam
nomes, contatos ou pedidos dos clientes fornecidos. Tokens, cookies e identificadores
de sessão não são exportados. A exportação confere as seis tabelas contra os arquivos
correspondentes e verifica o checksum do manual.

O código parte de `854b564`, com as correções locais documentadas nos relatórios.
Os arquivos registram ferramentas, fontes, status e reparações. `ok` significa
conclusão sob as verificações implementadas, não certificação semântica geral.
Parte das respostas é formatada pelo código a partir das consultas, incluindo
catálogo, resumos/negativas de pedido e orientação conservadora de devolução.

- [Rodada sintética](../validation/2026-11-03-delivery/report.md).
- [Integração e cenários originais](../validation/2026-11-04-original-demo/report.md).

O quarto exemplo sintético anterior foi movido para
`../validation/2026-11-03-delivery/not-selected/`, preservando sua transcrição e
captura como evidência adicional, fora desta seleção de cinco. As falhas anteriores
e suas correções permanecem nos relatórios; não foram apagadas do banco ou
transformadas em diálogos fictícios.

## Limites

Estes exemplos não comprovam atendimento geral, resistência ampla a injeções ou
baixa latência. O agente orienta; não executa devoluções ou pagamentos. Os arquivos
originais completos continuam fora do Git e das imagens Docker.
