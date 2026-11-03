"""Issue a short-lived demo credential without accepting customer selection over HTTP."""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.chat.access import issue_demo_access
from apps.customers.models import Customer


class Command(BaseCommand):
    help = (
        "Issue a customer-bound demo token locally. Output is a private credential; do not commit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--customer-id", type=int, required=True)
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        customer = Customer.objects.filter(pk=options["customer_id"]).first()
        if customer is None:
            raise CommandError("Cliente não encontrado.")
        if not 1 <= options["hours"] <= 168:
            raise CommandError("Validade deve ficar entre 1 e 168 horas.")
        access, token = issue_demo_access(customer, hours=options["hours"])
        self.stdout.write(
            json.dumps(
                {
                    "access_id": str(access.pk),
                    "access_token": token,
                    "expires_at": access.expires_at.isoformat(),
                }
            )
        )
