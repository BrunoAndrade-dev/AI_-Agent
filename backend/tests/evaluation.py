"""Shared read-only safety checks and metrics for local evaluation scripts."""

import hashlib
import time
from pathlib import Path

from apps.chat.ollama import OllamaClient
from apps.core.importing import TABLES, load_bundle
from apps.knowledge.models import PolicyDocument


def check_synthetic_environment(*, require_model: bool = True) -> None:
    """Refuse source drift, including private customer/order data, before export."""
    if require_model and OllamaClient().model != "qwen3:1.7b":
        raise RuntimeError("Expected qwen3:1.7b; no configuration changed.")
    directory = Path("/data/synthetic")
    bundle = load_bundle(directory)
    for table, (model, _) in TABLES.items():
        expected = bundle[table]
        actual = list(model.objects.values(*expected[0]))
        if len(actual) != len(expected) or not all(row in actual for row in expected):
            raise RuntimeError(f"Synthetic {table} mismatch; evaluation/export refused.")
    checksum = hashlib.sha256((directory / "policies-demo.pdf").read_bytes()).hexdigest()
    if not PolicyDocument.objects.filter(key="store-policies", sha256=checksum).exists():
        raise RuntimeError("Synthetic policy document mismatch; evaluation/export refused.")


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
