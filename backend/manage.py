"""Run Django management commands from the backend directory."""

import os
import sys


def main() -> None:
    """Configure the settings module and dispatch the requested command."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
