"""Import a versioned PDF into the local policy index."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from pypdf.errors import PyPdfError

from apps.knowledge.services import ingest_policies


class Command(BaseCommand):
    """Ingest policy passages without echoing their content to logs."""

    help = "Extract and index the store policy PDF with page/section provenance."

    def add_arguments(self, parser) -> None:
        parser.add_argument("path", type=Path)
        parser.add_argument("--document-version", required=True)
        parser.add_argument("--rebuild", action="store_true")

    def handle(self, *args, **options) -> None:
        try:
            result = ingest_policies(
                options["path"], version=options["document_version"], force=options["rebuild"]
            )
        except (OSError, ValueError, PyPdfError):
            raise CommandError(
                "Unable to index PDF; verify path, version and extractable text."
            ) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"Policies indexed: pages={result['pages']}, "
                f"chunks={result['chunks']}, changed={result['changed']}"
            )
        )
