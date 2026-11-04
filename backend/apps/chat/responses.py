"""Trusted response rendering for authorization, order snapshots and return guidance."""

import re

from apps.orders.models import Order


def catalog_snapshot_reply(results: list[dict]) -> str | None:
    """Render catalog-only facts without reinterpreting discounts or sales channels.

    The model still chooses queries and may request further tools. This renderer
    only formats their final, current-turn results; it does not rank suitability.
    """
    if not results or not all("products" in item or "product" in item for item in results):
        return None
    products = {}
    for item in results:
        for product in item.get("products", []):
            products[product["id"]] = product
        if item.get("product"):
            products[item["product"]["id"]] = item["product"]
    if not products:
        return (
            "Não encontrei produtos para os filtros consultados. "
            "Pode informar outro nome ou característica?"
        )
    blocks = []
    for product in products.values():
        status = {
            "active": "ativo",
            "discontinued": "descontinuado",
            "coming_soon": "em breve",
        }.get(product["status"], product["status"])
        availability = "Disponível" if product["available"] else "Indisponível para venda"
        lines = [
            f"{product['name']} (produto {product['id']}) — {availability}.",
            f"Status: {status}. Estoque registrado: {product['stock_quantity']}.",
        ]

        def brl(key: str) -> str:
            return product[key].replace(".", ",")

        if product["promotion"]:
            percent = product["promotion"]["discount_percent"].replace(".", ",")
            lines.append(
                f"De R$ {brl('table_price')} por R$ {brl('current_price')} "
                f"({percent}% de desconto sobre o preço de tabela)."
            )
            lines.append(
                f"PIX: R$ {brl('pix_price')}. O desconto de PIX não acumula com a promoção."
            )
        else:
            lines.append(f"Preço de tabela: R$ {brl('table_price')}. PIX: R$ {brl('pix_price')}.")
        if product.get("specs"):
            labels = {"strings": "Cordas", "electronics": "Eletrônica", "color": "Cor"}
            lines.append(
                "Características: "
                + "; ".join(
                    f"{labels.get(key, key.replace('_', ' '))}: {value}"
                    for key, value in product["specs"].items()
                )
            )
        blocks.append("\n".join(lines))
    if any(item.get("truncated") for item in results):
        blocks.append("Há mais resultados. Refine os filtros para consultar outras opções.")
    return "\n\n".join(blocks)


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
    relevant = [
        source
        for source in sources
        if asks_about_returns(source["section"]) or re.match(r"^4(?:\.|\s)", source["section"])
    ]
    passages = relevant or sources
    excerpts = "\n\n".join(source["text"] for source in passages)
    return (
        "Posso orientar sobre as condições, mas não aprovar ou executar uma devolução.\n\n"
        "Para analisar seu caso, preciso confirmar: a compra foi online ou na loja física? "
        "Em que data você recebeu o produto de fato? A entrega estimada não confirma recebimento."
        "\n\nO manual informa:\n" + excerpts
    )
