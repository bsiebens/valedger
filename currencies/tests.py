from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from .models import Currency, ConversionRate


class CurrencyModelTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
        self.eur = Currency.objects.create(code="EUR", name="Euro", symbol="€")

    def test_currency_str(self):
        self.assertEqual(str(self.usd), "USD")

    def test_convert_with_rate(self):
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.90"), date=timezone.now().date())
        converted_amount = self.usd.convert(to_currency="EUR", amount=Decimal("100.00"))
        self.assertEqual(converted_amount, Decimal("90.00"))

    def test_convert_with_rate_default_amount(self):
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.90"), date=timezone.now().date())
        converted_amount = self.usd.convert(to_currency="EUR")
        self.assertEqual(converted_amount, Decimal("0.90"))

    def test_convert_without_rate(self):
        # No conversion rate exists from USD to JPY
        Currency.objects.create(code="JPY", name="Japanese Yen", symbol="¥")
        original_amount = Decimal("100.00")
        converted_amount = self.usd.convert(to_currency="JPY", amount=original_amount)
        self.assertEqual(converted_amount, original_amount)

    def test_convert_uses_latest_rate(self):
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)

        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.85"), date=yesterday)
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.90"), date=today)  # This is the latest

        converted_amount = self.usd.convert(to_currency="EUR", amount=Decimal("10.00"))
        self.assertEqual(converted_amount, Decimal("9.00"))


class ConversionRateModelTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code="USD", name="US Dollar")
        self.eur = Currency.objects.create(code="EUR", name="Euro")
        self.date = timezone.now().date()
        self.rate = ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9000"), date=self.date)

    def test_conversion_rate_str(self):
        expected_str = f"USD:EUR 0.9000 ({self.date.isoformat()})"
        self.assertEqual(str(self.rate), expected_str)


class ConversionRateSignalTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code="USD", name="US Dollar")
        self.eur = Currency.objects.create(code="EUR", name="Euro")
        self.date = timezone.now().date()

    def test_reverse_rate_created_on_new_save(self):
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        self.assertTrue(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, factor=Decimal("1.0") / Decimal("0.9"), date=self.date).exists())

    def test_reverse_rate_deleted_on_delete(self):
        rate = ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        # The reverse rate should have been created by the post_save signal
        self.assertTrue(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, date=self.date).exists())
        rate.delete()
        self.assertFalse(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, date=self.date).exists())

    def test_update_existing_reverse_rate_factor_on_original_change(self):
        rate = ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        # Reverse rate EUR->USD with factor 1/0.9 should exist

        rate.factor = Decimal("0.8")
        rate.save()

        reverse_rate = ConversionRate.objects.get(from_currency=self.eur, to_currency=self.usd, date=self.date)
        self.assertEqual(reverse_rate.factor, (Decimal("1.0") / Decimal("0.8")).quantize(Decimal("0.0001")))

    def test_reverse_rate_factor_is_zero_if_original_factor_is_zero_on_create(self):
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.0"), date=self.date)
        self.assertTrue(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, factor=Decimal("0.0"), date=self.date).exists())
        reverse_rate = ConversionRate.objects.get(from_currency=self.eur, to_currency=self.usd, date=self.date)
        self.assertEqual(reverse_rate.factor, Decimal("0.0"))

    def test_reverse_rate_factor_is_zero_if_original_factor_is_zero_on_update(self):
        # Create initial rate with non-zero factor
        rate = ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        # Reverse rate should exist with reciprocal factor
        self.assertTrue(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, date=self.date).exists())

        # Update original rate's factor to zero
        rate.factor = Decimal("0.0")
        rate.save()

        # Reverse rate's factor should now be zero
        reverse_rate = ConversionRate.objects.get(from_currency=self.eur, to_currency=self.usd, date=self.date)
        self.assertEqual(reverse_rate.factor, Decimal("0.0"))

    def test_signal_idempotency_if_reverse_rate_with_correct_factor_exists(self):
        # Create the initial rate, which triggers the signal to create the reverse
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        initial_reverse_rate = ConversionRate.objects.get(from_currency=self.eur, to_currency=self.usd, date=self.date)
        self.assertEqual(initial_reverse_rate.factor, (Decimal("1.0") / Decimal("0.9")).quantize(Decimal("0.0001")))

        # Save the original rate again (or a new one with identical values). Signal should not modify the existing correct reverse rate.
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.9"), date=self.date)
        self.assertEqual(ConversionRate.objects.filter(from_currency=self.eur, to_currency=self.usd, date=self.date).count(), 1)  # Still only one reverse rate
        final_reverse_rate = ConversionRate.objects.get(from_currency=self.eur, to_currency=self.usd, date=self.date)
        self.assertEqual(final_reverse_rate.pk, initial_reverse_rate.pk)  # Ensure it's the same object
        self.assertEqual(final_reverse_rate.factor, (Decimal("1.0") / Decimal("0.9")).quantize(Decimal("0.0001")))  # Factor remains correct
