from decimal import Decimal
from django.test import TestCase
from django.db.utils import IntegrityError
from django.utils import timezone

from .models import Currency, ConversionRate


class CurrencyModelTests(TestCase):
    def setUp(self):
        # Base currency
        self.usd = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_base_currency=True)
        # Other currencies
        self.eur = Currency.objects.create(code="EUR", name="Euro", symbol="€")
        self.jpy = Currency.objects.create(code="JPY", name="Japanese Yen", symbol="¥")
        self.gbp = Currency.objects.create(code="GBP", name="British Pound", symbol="£")
        self.date = timezone.now().date()

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
        # No conversion rate exists from USD (base) to JPY
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

    def test_convert_to_currency_object(self):
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("0.90"), date=self.date)
        converted_amount = self.usd.convert(to_currency=self.eur, amount=Decimal("100.00"))
        self.assertEqual(converted_amount, Decimal("90.00"))

    def test_convert_from_non_base_to_base(self):
        ConversionRate.objects.create(from_currency=self.eur, to_currency=self.usd, factor=Decimal("1.10"), date=self.date)
        converted_amount = self.eur.convert(to_currency=self.usd, amount=Decimal("100.00"))
        self.assertEqual(converted_amount, Decimal("110.00"))

    def test_convert_between_non_base_currencies_via_base(self):
        ConversionRate.objects.create(from_currency=self.eur, to_currency=self.usd, factor=Decimal("1.10"), date=self.date)  # EUR -> USD
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.jpy, factor=Decimal("130.00"), date=self.date)  # USD -> JPY

        # EUR -> JPY via USD
        # 100 EUR * 1.10 (EUR/USD) * 130.00 (JPY/USD) = 14300 JPY
        converted_amount = self.eur.convert(to_currency=self.jpy, amount=Decimal("100.00"))
        self.assertEqual(converted_amount, Decimal("14300.00"))

    def test_convert_between_non_base_currencies_missing_first_leg_rate(self):
        # EUR -> USD rate is missing
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.jpy, factor=Decimal("130.00"), date=self.date)  # USD -> JPY
        original_amount = Decimal("100.00")
        converted_amount = self.eur.convert(to_currency=self.jpy, amount=original_amount)
        self.assertEqual(converted_amount, original_amount)  # Should return original amount

    def test_convert_between_non_base_currencies_missing_second_leg_rate(self):
        ConversionRate.objects.create(from_currency=self.eur, to_currency=self.usd, factor=Decimal("1.10"), date=self.date)  # EUR -> USD
        # USD -> JPY rate is missing
        original_amount = Decimal("100.00")
        converted_amount = self.eur.convert(to_currency=self.jpy, amount=original_amount)
        self.assertEqual(converted_amount, original_amount)  # Should return original amount

    def test_convert_to_same_currency_base(self):
        original_amount = Decimal("50.00")
        converted_amount = self.usd.convert(to_currency=self.usd, amount=original_amount)
        self.assertEqual(converted_amount, original_amount)

    def test_convert_to_same_currency_non_base(self):
        ConversionRate.objects.create(from_currency=self.eur, to_currency=self.usd, factor=Decimal("1.10"), date=self.date)
        ConversionRate.objects.create(from_currency=self.usd, to_currency=self.eur, factor=Decimal("1.0") / Decimal("1.10"), date=self.date)
        original_amount = Decimal("50.00")
        converted_amount = self.eur.convert(to_currency=self.eur, amount=original_amount)
        # Expecting 50.00 * 1.10 * (1/1.10) which is 50.00
        self.assertEqual(converted_amount.quantize(Decimal("0.0001")), original_amount.quantize(Decimal("0.0001")))

    def test_convert_invalid_to_currency_code_raises_does_not_exist(self):
        with self.assertRaises(Currency.DoesNotExist):
            self.usd.convert(to_currency="XXX", amount=Decimal("100.00"))

    def test_save_first_currency_becomes_base(self):
        Currency.objects.all().delete()  # Ensure no currencies exist
        eur = Currency.objects.create(code="EUR", name="Euro")
        self.assertTrue(eur.is_base_currency)

    def test_save_new_currency_when_base_exists(self):
        # self.usd is already base
        chf = Currency.objects.create(code="CHF", name="Swiss Franc")
        self.assertFalse(chf.is_base_currency)
        self.assertTrue(Currency.objects.get(code="USD").is_base_currency)

    def test_save_change_base_currency(self):
        self.assertTrue(self.usd.is_base_currency)
        self.assertFalse(self.eur.is_base_currency)

        self.eur.is_base_currency = True
        self.eur.save()

        self.assertTrue(Currency.objects.get(code="EUR").is_base_currency)
        self.assertFalse(Currency.objects.get(code="USD").is_base_currency)

    def test_save_existing_base_currency(self):
        self.assertTrue(self.usd.is_base_currency)
        self.usd.name = "US Dollar Updated"
        self.usd.save()

        self.assertTrue(Currency.objects.get(code="USD").is_base_currency)
        # Ensure other currencies are still not base
        self.assertFalse(Currency.objects.get(code="EUR").is_base_currency)

    def test_save_cannot_unset_last_base_currency(self):
        # Ensure only USD is base
        Currency.objects.exclude(pk=self.usd.pk).update(is_base_currency=False)
        self.usd.is_base_currency = True  # Make sure it's explicitly set before save
        self.usd.save()
        self.assertTrue(Currency.objects.get(pk=self.usd.pk).is_base_currency)

        # Try to save it as not base
        self.usd.is_base_currency = False
        self.usd.save()
        # It should remain base because it's the only one (or would be the only candidate if others existed but were false)
        self.assertTrue(Currency.objects.get(pk=self.usd.pk).is_base_currency)

    def test_save_non_base_currency_remains_non_base(self):
        self.assertFalse(self.eur.is_base_currency)
        self.eur.name = "Euro Updated"
        self.eur.save()
        self.assertFalse(Currency.objects.get(code="EUR").is_base_currency)
        self.assertTrue(Currency.objects.get(code="USD").is_base_currency)  # Original base remains


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
