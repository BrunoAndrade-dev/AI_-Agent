# Verificação do frontend — 03/11/2026

final result: passed

Este resultado se aplica somente à revisão visual e aos fluxos de interface
descritos abaixo. Não é aprovação geral do agente ou do modelo.

Escopo: adaptação visual e integração do chat. Este resultado não aprova a
qualidade geral do modelo local. O registro descreve a validação realizada antes
do commit `854b564`; não implica autorização para novos commits ou push.

## Referência e comparação

Referência fornecida pelo usuário: captura do protótipo Empório da Música no
Figma Make, com paleta clara e painel central de conversa (1230 × 693).
A imagem de referência está preservada no lado esquerdo da comparação abaixo.
Implementação observada em `http://localhost:3000`, viewport desktop 1231 × 800
e celular 390 × 844. Capturas têm largura útil menor quando há barra de rolagem.

Comparação conjunta: [referência e implementação](docs/validation/2026-11-03-frontend/images/comparison.jpg).
O desktop usa altura maior para mostrar o compositor completo; não se trata de
comparação pixel a pixel. Também foi capturado viewport 1230 × 693: a página tem
rolagem vertical, necessária para o conteúdo adicional de atendimento.

Adaptações intencionais: cores escuras solicitadas; conteúdo de catálogo, pedidos
e políticas no lugar de curadoria musical; controles reais de sessão e histórico;
ausência de botão de áudio sem recurso correspondente no produto.

## Revisão visual

- Tipografia: título serifado com trecho em itálico e fontes locais; texto de
  resposta em sans-serif de 15 px no desktop e 14 px no celular.
- Espaçamento: marca centralizada, painel com moldura dupla, sugestões e campo de
  envio. No celular os controles se compactam sem rolagem horizontal (390/390 px).
- Cores: café, cobre e creme, mantendo separação entre fundo, painel e mensagens.
- Imagem: textura discreta em WebP de 13.238 bytes; original PNG removido do
  diretório público para evitar carregar um arquivo de aproximadamente 2 MB.
- Conteúdo: nenhuma conversa de exemplo é apresentada como resposta real.
  A abertura é um estado de boas-vindas; as respostas vêm da API.
- Elementos musicais: seis ícones pequenos, lentos e nas bordas. No celular,
  alguns ficam ocultos. O botão de pausa foi observado com `animation-name:none`
  nos seis elementos. Há regra CSS para movimento reduzido.
- Histórico mobile: dialog legível, foco inicial no fechamento; Escape fecha e
  devolve o foco ao botão que abriu a janela.

As capturas desktop e mobile também permitem inspecionar os detalhes do painel,
compositor e diálogo. Nenhuma divergência visual P0/P1/P2 foi identificada na
comparação da adaptação autorizada. Não houve correção visual após essa comparação.

## Integração observada

A sessão já autenticada foi preservada, sem logout ou troca do código existente.
Foi criada uma conversa de teste pela própria interface, sem modificar conversas
anteriores. Seus dois turnos permanecem disponíveis no histórico.

1. A consulta de trocas/devoluções atingiu o tempo limite do modelo e retornou
   turno persistido com mensagem de indisponibilidade e opção de nova tentativa.
2. O envio seguinte, sobre violões até R$ 1.000, retornou Violão Exemplo Nylon,
   estoque de cinco unidades, preço atual e PIX de R$ 900,00 e oferta de 10%.
3. Recarregar a página recuperou a sessão e os dois turnos.
4. Histórico mostrou a conversa atual e a anterior. Nova conversa voltou ao
   estado inicial sem criar outra linha até ocorrer um envio.
5. Não foram observados erros ou avisos no console na leitura realizada.

Referências documentais não puderam ser verificadas com resposta real nesta rodada,
pois a consulta correspondente falhou na inferência. Login/logout não foram
executados no navegador para preservar o escopo da sessão existente.

## Verificação técnica

- `npm test`: cinco testes passaram.
- `npm run typecheck`: passou.
- `npm run build`: passou fora das restrições de subprocessos do sandbox.
- Imagem Docker do frontend construída e serviço iniciado na porta 3000.
- `git diff --check`: passou.

O backend não foi alterado; a suíte existente de 111 testes não foi repetida nesta
etapa. Os testes novos cobrem transporte HTTP com respostas controladas, não a
qualidade semântica do LLM. A latência e o timeout do Ollama continuam como
limitação real a investigar separadamente.

Evidências: [desktop](docs/validation/2026-11-03-frontend/images/desktop.jpg),
[celular em espera](docs/validation/2026-11-03-frontend/images/mobile.jpg),
[histórico](docs/validation/2026-11-03-frontend/images/history-mobile.jpg).

## Revisão complementar para entrega

A revisão das respostas do catálogo identificou um problema de legibilidade:
quebras de linha vindas da API eram colapsadas em um único parágrafo (P2).
O CSS de `.reply-copy p` passou a usar `white-space: pre-line`, preservando o texto
e a segurança do Markdown. Após recarregar, o estilo computado e a captura do
exemplo PIX confirmaram a separação das linhas.

Antes: [parágrafo colapsado](docs/validation/2026-11-03-delivery/images/before-line-breaks.jpg).
Depois: [resposta com linhas preservadas](docs/examples/images/01-catalogo-e-pix.jpg).
As capturas mostram estados diferentes da conversa e não servem para comparação
pixel a pixel. A mudança avaliada é a separação de campos dentro da resposta.
O resultado inicial acima permanece histórico; a revisão funcional complementar
e seus limites estão no [relatório de entrega](docs/validation/2026-11-03-delivery/report.md).
