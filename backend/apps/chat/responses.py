"""Trusted response rendering for authorization, order snapshots and return guidance."""

import re

from apps.orders.models import Order


def scoped_order_reply(results: list[dict]) -> str | None:
    """Keep authorization denials independent from the model's interpretation."""
    if not results or not all(
        item.get("reason") in {"not_found_in_customer_scope", "customer_session_required"}
        for item in results
    ):
        return None
    if any(item["reason"] == "customer_session_required" for item in results):
        return "É necessário estar em uma sessão de cliente identificada para consultar pedidos."
    return "Não encontrei esse pedido nesta sessão. Confira o número do pedido."


def order_snapshot_reply(results: list[dict]) -> str | None:
    """Present an order-only lookup without inventing receipt or carrier events."""
    if not results or not all(item.get("found") and "order_id" in item for item in results):
        return None
    snapshots = []
    for order in results:
        status = Order.Status(order["status"]).label
        payment = Order.PaymentMethod(order["payment_method"]).label
        total = order["total_brl"].replace(".", ",")
        estimate = order["estimated_delivery"] or "não informada"
        tracking = order["tracking_code"] or "não informado"
        snapshots.append(
            f"Pedido {order['order_id']} — status registrado: {status}.\n"
            f"Total: R$ {total}. Pagamento: {payment}.\n"
            f"Data do pedido: {order['order_date']}.\n"
            f"Entrega estimada: {estimate} (estimativa, não confirmação de recebimento).\n"
            "Data real de recebimento: não informada.\n"
            f"Rastreio registrado: {tracking}.\n"
            "Estas informações são do banco local; a transportadora não foi consultada."
        )
    return "\n\n".join(snapshots)


def asks_about_returns(text: str) -> bool:
    """Identify explicit Portuguese return/withdrawal topics for a business guard."""
    return bool(re.search(r"\b(?:devol\w*|arrepend\w*)\b", text, re.IGNORECASE))


def return_guidance(sources: list[dict]) -> str:
    """Quote the actual policy and ask for missing case facts, without eligibility claims.

    The prototype does not yet track verified channel/receipt facts or authorize
    returns. Keep that boundary deterministic instead of asking the LLM to approve.
    """
    relevant = [source for source in sources if asks_about_returns(source["section"])]
    passages = relevant or sources
    excerpts = "\n\n".join(source["text"] for source in passages)
    return (
        "Posso orientar sobre as condições, mas não aprovar ou executar uma devolução.\n\n"
        "Para analisar seu caso, preciso confirmar: a compra foi online ou na loja física? "
        "Em que data você recebeu o produto de fato? A entrega estimada não confirma recebimento."
        "\n\nO manual informa:\n" + excerpts
    )
