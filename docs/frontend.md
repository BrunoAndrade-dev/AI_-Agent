# Frontend de atendimento

Abra [http://localhost:3000](http://localhost:3000). Use `localhost` também no
backend e no Swagger para manter o mesmo host dos cookies. O navegador usa
`NEXT_PUBLIC_API_BASE_URL` (padrão `http://localhost:8000/api`). Essa variável é
pública e não deve conter credenciais.

O Compose também permite `http://localhost:3001` para desenvolvimento local,
incluindo cookies e CSRF. O Next.js pode escolher essa porta quando 3000 já está
ocupada pelo frontend Docker. O backend permanece em `http://localhost:8000/api`.
Outras origens continuam exigindo configuração explícita.

Para os produtos e políticas do desafio, use o [modo original](original-demo.md).
Ele aponta a mesma API para um banco separado e usa cookie próprio; ao alternar,
recarregue a página e entre com um código emitido na base correspondente.

## Execução

Com o ambiente já configurado, execute `docker compose up -d --build frontend`.
Banco, backend e Ollama precisam estar ativos para o atendimento completo.
Os diretórios `frontend/src` e `frontend/public` são montados somente para leitura
no container para atualização durante o desenvolvimento. Mudanças de dependências
exigem reconstrução da imagem. Os volumes de banco e modelos permanecem separados.

Para emitir um código demonstrativo local com os dados sintéticos:

```sh
docker compose exec backend python manage.py create_demo_access --customer-id 1 --hours 24
```

Cole apenas o `access_token` no campo de acesso. Ele não é salvo em localStorage,
sessionStorage ou configuração pública. A sessão usa cookies e CSRF; o cliente
não escolhe sua identidade por parâmetro HTTP. Ao recarregar, o frontend recupera
a sessão e a conversa mais recente. Encerrar e entrar novamente cria outro escopo
de acesso ao histórico, conforme o contrato do backend.

## Preparar uma demonstração

Antes de apresentar, confira os serviços e envie uma saudação pelo CLI para
carregar o modelo:

```sh
docker compose exec backend python manage.py chat_store --message "Olá"
```

`--check-model` verifica a instalação, mas não substitui o carregamento. O
adaptador solicita retenção de cinco minutos entre chamadas; depois de um período
ocioso, pode ocorrer novo carregamento. A medição registrada em
`docs/validation/2026-11-03-delivery/latency.jsonl` levou 136,99 s a frio e
38,49/37,54 s nas repetições. Aquecer não garante respostas rápidas nem impede
timeout. Evite gerar consultas de avaliação simultaneamente à apresentação.

## Comportamento

- Sugestões preenchem o campo; o usuário confirma o envio.
- Histórico permite retomar conversas da sessão e carregar outras páginas.
- Nova conversa é criada no servidor somente no primeiro envio.
- Enter envia; Shift + Enter insere uma linha. O limite é de 2.000 caracteres.
- Durante um envio, os controles impedem ações concorrentes.
- Falha de rede mantém o identificador da requisição para repetir sem duplicação;
  também é possível conferir se o resultado já apareceu no histórico.
- Respostas de falha persistidas pelo backend são exibidas como turnos.
  Uma nova tentativa de geração é um novo envio, identificado como tal na UI.
- Sessão expirada limpa os dados privados exibidos. Limites de frequência e de
  25 turnos por conversa têm estados próprios.
- Referências documentais são exibidas quando retornadas pela API. Markdown não
  executa HTML nem carrega imagens ou links externos.

O visual adapta a referência fornecida para atendimento de instrumentos: café,
cobre e creme, tipografia local e textura WebP de aproximadamente 13 KB.
Seis ícones musicais pequenos usam animações CSS lentas, com menos elementos no
celular, controle de pausa e suporte a `prefers-reduced-motion`.

## Verificação

```sh
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

Os cinco testes de transporte cobrem rotação CSRF, preservação do identificador,
falhas persistidas, indisponibilidade de rede e limitação de frequência.
Evidências visuais e os limites do teste real estão em `design-qa.md` na raiz.
O frontend não corrige a qualidade semântica ou a latência do modelo local.
