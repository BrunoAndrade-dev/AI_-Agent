"""Export only the two approved original-material UI scenarios, never customer data.

Requires EMPORIO_EXAMPLES_ACCESS_ID for the locally issued evaluation access.
The access token, user ID, customer ID and session IDs are never exported.
"""

import hashlib
import json
import os
from pathlib import Path

from django.conf import settings

from apps.chat.models import Conversation, DemoAccess
from apps.core.importing import TABLES, load_bundle
from apps.customers.models import Customer
from apps.knowledge.models import PolicyDocument

if settings.DATABASES["default"]["NAME"] != "emporio_original":
    raise RuntimeError("Original demonstration database required; export refused.")
bundle = load_bundle(Path("/data/private"))
for table, (model, _) in TABLES.items():
    expected = bundle[table]
    actual = list(model.objects.values(*expected[0]))
    if len(actual) != len(expected) or not all(row in actual for row in expected):
        raise RuntimeError(f"Original {table} source mismatch; export refused.")
checksum = hashlib.sha256(Path("/data/private/policies.pdf").read_bytes()).hexdigest()
if not PolicyDocument.objects.filter(key="store-policies", sha256=checksum).exists():
    raise RuntimeError("Original manual required; export refused.")

titles = {
    "Quanto custa o Takamine GD20? Ele está disponível?": "04-catalogo-original",
    "Qual o horário de funcionamento aos sábados e aos domingos?": "05-politicas-originais",
}
allowed = set(titles) | {
    "E no PIX?",
    "Qual é a regra do PIX quando o produto já está em promoção?",
}
access = DemoAccess.objects.get(pk=os.environ["EMPORIO_EXAMPLES_ACCESS_ID"])
private_contacts = [
    value for row in Customer.objects.values_list("email", "phone") for value in row if value
]
records = []
selected = set()
for conversation in Conversation.objects.filter(owner=access.user).prefetch_related("turns"):
    turns = list(conversation.turns.all())
    if not turns or turns[0].user_message not in titles:
        continue
    name = titles[turns[0].user_message]
    if name in selected:
        continue
    if any(turn.user_message not in allowed for turn in turns):
        raise RuntimeError("Unexpected question; manual privacy review required.")
    if any(contact in turn.text for contact in private_contacts for turn in turns):
        raise RuntimeError("Customer contact detected; export refused.")
    records.append(
        {
            "example": name,
            "material": "original",
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
    selected.add(name)
if len(records) != 2 or len({row["example"] for row in records}) != 2:
    raise RuntimeError("Two distinct original-material scenarios required; no partial export.")
print(json.dumps(sorted(records, key=lambda row: row["example"]), ensure_ascii=False), flush=True)
