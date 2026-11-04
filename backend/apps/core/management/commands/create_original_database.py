"""Create a separate original-material database without replacing existing data."""

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from psycopg import sql

ORIGINAL_DATABASE = "emporio_original"


class Command(BaseCommand):
    help = "Create emporio_original if absent; never drop or overwrite a database."

    def handle(self, *args, **options):
        config = settings.DATABASES["default"]
        try:
            with psycopg.connect(
                dbname="postgres",
                user=config["USER"],
                password=config["PASSWORD"],
                host=config["HOST"],
                port=config["PORT"],
                autocommit=True,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s", (ORIGINAL_DATABASE,)
                    )
                    if cursor.fetchone():
                        self.stdout.write("Original database already exists; no changes made.")
                        return
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(ORIGINAL_DATABASE))
                    )
        except psycopg.Error:
            raise CommandError(
                "Unable to create original database. Check database access and CREATEDB permission."
            ) from None
        self.stdout.write(self.style.SUCCESS("Created emporio_original; demo database preserved."))
