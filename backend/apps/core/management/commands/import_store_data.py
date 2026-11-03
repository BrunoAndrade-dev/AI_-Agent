"""Expose validated CSV ingestion as a Django management command."""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.core.importing import ImportValidationError, import_bundle


class Command(BaseCommand):
    """Import six CSVs with no partial writes and no customer values in output."""

    help = (
        "Validate and upsert store CSVs atomically; existing rows absent from files are retained."
    )

    def add_arguments(self, parser) -> None:
        """Declare source directory and optional rollback-only execution."""
        parser.add_argument("--directory", type=Path, required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        """Report only safe validation coordinates, counts and aggregate warnings."""
        try:
            report = import_bundle(options["directory"], dry_run=options["dry_run"])
        except ImportValidationError as error:
            raise CommandError(str(error)) from None
        except (OSError, UnicodeError, csv.Error):
            raise CommandError(
                "Unable to read CSV bundle; check filenames, UTF-8 and CSV syntax."
            ) from None
        except DatabaseError:
            # Database error details may contain an entire source row, including PII.
            raise CommandError(
                "Database import failed; all changes rolled back. "
                "Check database availability and constraints."
            ) from None
        for table, counts in report["counts"].items():
            self.stdout.write(
                f"{table}: created={counts['created']}, existing={counts['existing']}"
            )
        for warning in report["warnings"]:
            self.stdout.write(self.style.WARNING(warning))
        outcome = (
            "Dry run complete; no changes persisted." if report["dry_run"] else "Import committed."
        )
        self.stdout.write(self.style.SUCCESS(outcome))
