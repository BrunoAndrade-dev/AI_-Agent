"""Read-only real-model evaluation on the verified public synthetic fixture.

Run through manage.py shell; never import into a production process.
"""

import json
import time
from dataclasses import asdict

from apps.chat.agent import StoreAgent
from apps.chat.tools import AgentContext
from tests.evaluation import MeasuredClient, check_synthetic_environment

check_synthetic_environment()

client = MeasuredClient()

with client.opener.open(client.base_url + "/api/ps", timeout=10) as response:
    loaded = json.loads(response.read())
print(
    json.dumps(
        {
            "event": "initial_state",
            "loaded_models": [m["name"] for m in loaded.get("models", [])],
        }
    ),
    flush=True,
)
for iteration in range(3):
    client.metrics = []
    agent = StoreAgent(context=AgentContext(customer_id=1), client=client)
    started = time.monotonic()
    reply = agent.reply("Qual o preço do produto 1 e quanto fica no PIX?")
    print(
        json.dumps(
            {
                "iteration": iteration + 1,
                "seconds": round(time.monotonic() - started, 2),
                "reply": asdict(reply),
                "metrics": client.metrics,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
