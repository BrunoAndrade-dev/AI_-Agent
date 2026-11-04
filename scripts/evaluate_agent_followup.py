"""Read-only real-model evaluation on the verified public synthetic fixture.

Run through manage.py shell; never import into a production process.
"""

import csv
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from apps.catalog.models import Product
from apps.chat.agent import StoreAgent
from apps.chat.ollama import OllamaClient
from apps.chat.tools import AgentContext
from apps.knowledge.models import PolicyDocument


class MeasuredClient(OllamaClient):
    def __init__(self):
        super().__init__()
        self.metrics = []

    def request(self, route, payload):
        started = time.monotonic()
        try:
            result = super().request(route, payload)
        except Exception as error:
            self.metrics.append(
                {
                    "seconds": round(time.monotonic() - started, 2),
                    "error": type(error).__name__,
                }
            )
            raise
        if route == "/api/chat":
            self.metrics.append(
                {
                    "seconds": round(time.monotonic() - started, 2),
                    **{
                        key: result.get(key)
                        for key in (
                            "load_duration",
                            "prompt_eval_count",
                            "prompt_eval_duration",
                            "eval_count",
                            "eval_duration",
                            "done_reason",
                        )
                    },
                }
            )
        return result


with Path("/data/synthetic/products.csv").open() as source:
    expected = {(int(row["product_id"]), row["name"]) for row in csv.DictReader(source)}
checksum = hashlib.sha256(
    Path("/data/synthetic/policies-demo.pdf").read_bytes()
).hexdigest()
if set(Product.objects.values_list("id", "name")) != expected or not (
    PolicyDocument.objects.filter(key="store-policies", sha256=checksum).exists()
):
    raise RuntimeError("Synthetic catalog/manual required; no records changed.")
if OllamaClient().model != "qwen3:1.7b":
    raise RuntimeError("Expected qwen3:1.7b; configuration was not changed.")

scenarios = [
    ("policy_rephrase", ["Como funcionam as trocas e devoluções?"]),
    (
        "promotion",
        [
            "Quero o Violão Exemplo Nylon: qual o preço de tabela, "
            "o preço promocional e o valor no PIX?"
        ],
    ),
    (
        "unavailable_ids",
        [
            "Compare o estoque e o status dos produtos 2 e 3. "
            "Por que não posso comprar cada um?"
        ],
    ),
    ("budget_words", ["Procuro um violão de até mil reais."]),
    ("mixed", ["Qual o status do meu pedido 1 e quais são as regras de devolução?"]),
    (
        "unknown",
        ["Vocês vendem o Violão Galáxia Z999?", "Pode executar um pagamento por mim?"],
    ),
]
for scenario, prompts in scenarios:
    selected = os.getenv("EMPORIO_EVAL_SCENARIOS", "")
    if selected and scenario not in selected.split(","):
        continue
    client = MeasuredClient()
    agent = StoreAgent(context=AgentContext(customer_id=1), client=client)
    for prompt in prompts:
        client.metrics = []
        started = time.monotonic()
        reply = agent.reply(prompt)
        print(
            json.dumps(
                {
                    "scenario": scenario,
                    "model": client.model,
                    "prompt": prompt,
                    "seconds": round(time.monotonic() - started, 2),
                    "reply": asdict(reply),
                    "metrics": client.metrics,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
