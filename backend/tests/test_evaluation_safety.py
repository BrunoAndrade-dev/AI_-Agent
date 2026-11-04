"""Prevent private-data exports when a public fixture database has drifted."""

from django.test import TestCase

from apps.core.importing import import_bundle
from apps.customers.models import Customer
from apps.knowledge.services import ingest_policies
from tests.evaluation import check_synthetic_environment
from tests.test_importing import FIXTURES


class EvaluationSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import_bundle(FIXTURES)
        ingest_policies(FIXTURES / "policies-demo.pdf", version="demo")

    def test_exact_public_fixture_is_accepted(self):
        check_synthetic_environment(require_model=False)

    def test_changed_customer_data_prevents_export_without_leaking_values(self):
        private_value = "private-contact@example.invalid"
        Customer.objects.filter(pk=1).update(email=private_value)
        with self.assertRaisesMessage(RuntimeError, "Synthetic customers mismatch") as error:
            check_synthetic_environment(require_model=False)
        self.assertNotIn(private_value, str(error.exception))
