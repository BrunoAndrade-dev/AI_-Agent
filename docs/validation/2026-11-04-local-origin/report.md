# Conexão local na porta 3001 — 04/11/2026

A interface foi aberta em `http://localhost:3001`, enquanto a API aceitava somente
`http://localhost:3000`. O GET de sessão respondia 200, mas sem permissão CORS
para 3001; o navegador bloqueava a leitura e a tela mostrava falha de conexão.

O Compose passou a acrescentar a origem local 3001 às listas de CORS e CSRF,
preservando os valores configurados no `.env`. Não foram habilitados curingas,
origens públicas ou alterações no banco. Somente o backend foi recriado, mantendo
o modo original e seu cookie próprio.

Verificações:

- HTTP real: 200, `Access-Control-Allow-Origin: http://localhost:3001` e
  `Access-Control-Allow-Credentials: true`.
- Teste direcionado de bootstrap, login e escrita com CSRF nas portas 3000 e 3001:
  aprovado. Origem externa não autorizada continuou recebendo 403 na escrita.
- Navegador em `http://localhost:3001`: sessão e histórico original recuperados;
  nenhum erro/aviso observado no console da nova aba.
- Evidências: `tests.txt` e `connected-3001.jpg`.

A suíte completa não foi repetida nesta correção de configuração. Não houve
alteração do `.env`, volumes, dados ou tokens existentes, nem commit/push.
