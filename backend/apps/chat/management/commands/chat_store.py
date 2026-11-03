"""Local operator-only entrypoint for real agent conversations."""

from django.core.management.base import BaseCommand, CommandError

from apps.chat.agent import StoreAgent
from apps.chat.ollama import ModelUnavailable, OllamaClient
from apps.chat.tools import AgentContext
from apps.customers.models import Customer


class Command(BaseCommand):
    """Run a local CLI; customer selection is not a public authentication mechanism."""

    help = "Chat locally with the store agent. No customer contacts are printed."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--message", help="Run a single message instead of interactive mode.")
        parser.add_argument(
            "--customer-id", type=int, help="Trusted local operator selects a demo customer."
        )
        parser.add_argument("--check-model", action="store_true")

    def handle(self, *args, **options) -> None:
        customer_id = options["customer_id"]
        if customer_id is not None and not Customer.objects.filter(pk=customer_id).exists():
            raise CommandError("Demo customer not found.")
        client = OllamaClient()
        if options["check_model"]:
            try:
                result = client.check_model()
            except ModelUnavailable:
                raise CommandError(
                    "Ollama unavailable or configured model not downloaded."
                ) from None
            if not result["supports_tools"]:
                raise CommandError("Configured model does not advertise tool support.")
            self.stdout.write(f"Model {result['model']}: tools supported.")
            return
        agent = StoreAgent(context=AgentContext(customer_id=customer_id), client=client)
        if options["message"]:
            reply = agent.reply(options["message"])
            self.stdout.write(reply.text)
            if reply.status != "ok":
                raise CommandError(f"Agent outcome: {reply.status}")
            return
        self.stdout.write("Empório da Música — digite /sair para encerrar.")
        while True:
            try:
                message = input("Você: ")
            except (EOFError, KeyboardInterrupt):
                break
            if message.strip().lower() == "/sair":
                break
            self.stdout.write(f"Loja: {agent.reply(message).text}")
