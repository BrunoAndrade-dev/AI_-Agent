"""Check safe, idempotent creation of the separate demonstration database."""

from io import StringIO
from unittest.mock import MagicMock, patch

import psycopg
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

CONNECT = "apps.core.management.commands.create_original_database.psycopg.connect"


class OriginalDatabaseTests(SimpleTestCase):
    def test_existing_database_is_not_overwritten(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        with patch(CONNECT, return_value=connection):
            call_command("create_original_database", stdout=StringIO())
        self.assertEqual(cursor.execute.call_count, 1)

    def test_only_the_named_database_is_created(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        with patch(CONNECT, return_value=connection):
            call_command("create_original_database", stdout=StringIO())
        self.assertEqual(cursor.execute.call_count, 2)
        statement = cursor.execute.call_args.args[0].as_string()
        self.assertEqual(statement, 'CREATE DATABASE "emporio_original"')
        self.assertNotIn("DROP", statement)

    def test_database_error_does_not_expose_credentials(self):
        with patch(CONNECT, side_effect=psycopg.OperationalError("private password")):
            with self.assertRaisesMessage(
                CommandError, "Unable to create original database"
            ) as error:
                call_command("create_original_database", stdout=StringIO())
        self.assertNotIn("private password", str(error.exception))
