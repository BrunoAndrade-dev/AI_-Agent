"""Revoke a demonstration credential and all browser access using it."""

import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.chat.models import DemoAccess


class Command(BaseCommand):
    help = "Revoke demo access by its public access_id; preserves conversation records."

    def add_arguments(self, parser):
        parser.add_argument("access_id", type=uuid.UUID)

    def handle(self, *args, **options):
        if not DemoAccess.objects.filter(pk=options["access_id"]).update(is_active=False):
            raise CommandError("Acesso não encontrado.")
        self.stdout.write("Acesso revogado.")
