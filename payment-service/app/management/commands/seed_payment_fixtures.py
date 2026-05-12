import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Payment, PaymentTransaction


class Command(BaseCommand):
    help = "Seed payment fixtures (idempotent)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "payment_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        count = 0
        for item in payload.get("payments", []):
            pid = int(item["id"])
            defaults = {
                "order_id": int(item["order_id"]),
                "amount": item["amount"],
                "overall_status": item["overall_status"],
                "payment_method": item.get("payment_method", "cod"),
            }
            Payment.objects.update_or_create(id=pid, defaults=defaults)
            count += 1

        txn_count = 0
        for item in payload.get("transactions", []):
            payment_id = int(item["payment_id"])
            try:
                payment = Payment.objects.get(id=payment_id)
                PaymentTransaction.objects.get_or_create(
                    transaction_code=item["transaction_code"],
                    defaults={
                        "payment": payment,
                        "transaction_note": item.get("transaction_note", ""),
                    }
                )
                txn_count += 1
            except Payment.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {count} payments and {txn_count} transactions"
        ))
