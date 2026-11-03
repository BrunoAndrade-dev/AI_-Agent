# Modelo local

O Django acessa o serviço em `http://ollama:11434` na rede Docker. A porta do
Ollama não é publicada no host. Os modelos ficam no volume `ollama_data`.

O runtime é Ollama 0.40.13, fixado por digest, com cloud desativado. O candidato
é `qwen3:4b`, ainda sem validação de qualidade/memória. Após bloqueios de rede e
quedas do ambiente na nuvem, a validação será feita localmente com Docker.

```sh
docker compose exec -e OLLAMA_HOST=http://127.0.0.1:11434 ollama ollama pull qwen3:4b
docker compose exec -e OLLAMA_HOST=http://127.0.0.1:11434 ollama ollama list
```

GPU não é presumida. Consulte `docs/agent.md` para configuração, CLI e limitações.
Um servidor saudável sem modelo instalado ainda não responde conversas.
