# Automação

Scripts locais de desenvolvimento e validação. Importação e operações do domínio
são comandos de gerenciamento Django.

- `validate_agent.py`: regressão conhecida com catálogo e manual sintéticos.
- `evaluate_agent_followup.py`: perguntas adicionais e métricas por chamada.
- `measure_agent_latency.py`: três consultas iguais, com registro do estado inicial
  do modelo; não descarrega o modelo nem altera configurações.
- `evaluate_original_data.py`: avaliação em banco temporário com arquivos privados.
  Sua saída pode conter informações originais; salvar somente em `.runtime/`.
- `validate_chat_api.py`: fluxo HTTP com acesso temporário e limpeza própria.
- `export_demo_conversations.py`: exportação somente de leitura de quatro exemplos
  sintéticos da rodada de validação anterior, após conferir as fontes.
- `export_original_examples.py`: exporta somente os dois cenários aprovados com
  material original, valida a base e recusa contatos dos clientes na resposta.
- `test_swagger_csrf.mjs`: verificação do tratamento de CSRF no Swagger.

Os scripts Python são executados pelo ambiente Django, por exemplo:

```sh
docker compose exec -T backend python manage.py shell < scripts/measure_agent_latency.py
```

São avaliações locais, não verificações automáticas de qualidade geral do modelo.
Não importar originais sobre a demonstração sintética.

Os scripts de avaliação sintética compartilham verificações e métricas em
`backend/tests/evaluation.py`. Eles recusam a base original; para executá-los
enquanto ela estiver ativa na API, use um container avulso com `compose.yaml`
sem o arquivo adicional, preservando a API original em execução.
