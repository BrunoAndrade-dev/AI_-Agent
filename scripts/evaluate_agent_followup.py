"""Read-only real-model evaluation on the verified public synthetic fixture.

Run through manage.py shell; never import into a production process.
"""

import json
import os
import time
from dataclasses import asdict

from apps.chat.agent import StoreAgent
from apps.chat.tools import AgentContext
from tests.evaluation import MeasuredClient, check_synthetic_environment

check_synthetic_environment()

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
        ["Compare o estoque e o status dos produtos 2 e 3. Por que não posso comprar cada um?"],
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
