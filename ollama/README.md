# Modelo local

O Django acessa o serviço em `http://ollama:11434` na rede Docker. A porta do
Ollama não é publicada no host. Os modelos ficam no volume `ollama_data`.

Após escolher e validar um modelo, configurar `OLLAMA_MODEL` no `.env` e executar:

```sh
docker compose exec ollama ollama pull NOME_DO_MODELO
docker compose exec ollama ollama list
```

O modelo, seus requisitos de memória e desempenho ainda serão validados.
GPU não é presumida pela configuração inicial.
