"""Read-only export of four UI examples from a verified synthetic database.

Set EMPORIO_EXAMPLES_SINCE to the timezone-aware start time of the UI run.
No access credentials, session identifiers or conversation UUIDs are exported.
"""

import json
import os
from datetime import datetime

from apps.chat.models import Conversation
from tests.evaluation import check_synthetic_environment

check_synthetic_environment(require_model=False)
since = datetime.fromisoformat(os.environ["EMPORIO_EXAMPLES_SINCE"])
if since.tzinfo is None:
    raise RuntimeError("A timezone-aware start time is required.")
titles = {
    "Quais violões disponíveis até R$ 1000?": "01-catalogo-e-pix",
    "Qual o status e o total do meu pedido 1?": "02-pedidos-e-privacidade",
    "Qual o status do meu pedido 1 e quais são as regras de devolução?": "03-devolucao-e-politicas",
    "Compare o estoque e o status dos produtos 2 e 3. Por que não posso comprar cada um?": (
        "04-indisponibilidade-e-escopo"
    ),
}
records = []
for conversation in Conversation.objects.filter(created_at__gte=since).prefetch_related("turns"):
    turns = list(conversation.turns.all())
    if not turns or turns[0].user_message not in titles:
        continue
    if conversation.customer_id != 1:
        raise RuntimeError("Expected synthetic customer 1; export refused.")
    records.append(
        {
            "example": titles[turns[0].user_message],
            "turns": [
                {
                    "user_message": turn.user_message,
                    "text": turn.text,
                    "status": turn.status,
                    "sources": turn.sources,
                    "tools_used": turn.tools_used,
                    "validation_errors": turn.validation_errors,
                    "created_at": turn.created_at.isoformat(),
                }
                for turn in turns
            ],
        }
    )
if len(records) != 4 or len({r["example"] for r in records}) != 4:
    raise RuntimeError("Exactly four distinct UI examples required; no partial export.")
print(
    json.dumps(sorted(records, key=lambda row: row["example"]), ensure_ascii=False),
    flush=True,
)
