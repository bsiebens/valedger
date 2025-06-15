from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import ConversionFactor, Currency


class CurrencyModelTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_base_currency=True)
        self.eur = Currency.objects.create(code="EUR", name="Euro", symbol="€")
        self.gbp = Currency.objects.create(code="GBP", name="Pound Sterling", symbol="£")

    def test_str(self):
        self.assertEqual(str(self.usd), "USD")
        self.assertEqual(str(self.eur), "EUR")
        self.assertEqual(str(self.gbp), "GBP")

    def test_only_one_base_currency(self):
        self.eur.is_base_currency = True
        self.eur.save()

        self.usd.refresh_from_db()
        self.eur.refresh_from_db()

        self.assertTrue(self.eur.is_base_currency)
        self.assertFalse(self.usd.is_base_currency)

    def test_save_sets_base_if_none_exists(self):
        Currency.objects.update(is_base_currency=False)
        self.assertEqual(Currency.objects.filter(is_base_currency=True).count(), 0)

        self.gbp.refresh_from_db()
        self.gbp.save()
        self.assertTrue(self.gbp.is_base_currency)

    def test_delete_base_promotes_another(self):
        self.usd.delete()
        self.eur.refresh_from_db()
        self.gbp.refresh_from_db()

        self.assertTrue(self.eur.is_base_currency or self.gbp.is_base_currency)


class ConversionPathTests(TestCase):
    def setUp(self):
        # Create base currencies
        self.usd = Currency.objects.create(code="USD")
        self.eur = Currency.objects.create(code="EUR")
        self.gbp = Currency.objects.create(code="GBP")
        self.cad = Currency.objects.create(code="CAD")
        self.inr = Currency.objects.create(code="INR")
        self.cny = Currency.objects.create(code="CNY")
        self.jpy = Currency.objects.create(code="JPY")
        self.krw = Currency.objects.create(code="KRW")
        self.aud = Currency.objects.create(code="AUD")
        self.zzz = Currency.objects.create(code="ZZZ")  # Disconnected

        # Define conversions (some one-way, some requiring reversal)
        ConversionFactor.objects.create(from_currency=self.eur, to_currency=self.usd, factor=1.2, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.gbp, to_currency=self.eur, factor=1.1, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.usd, to_currency=self.cad, factor=1.25, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.cad, to_currency=self.eur, factor=0.9, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.eur, to_currency=self.inr, factor=88, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.inr, to_currency=self.cny, factor=0.12, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.cny, to_currency=self.jpy, factor=17, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.jpy, to_currency=self.krw, factor=10, date=timezone.now())
        ConversionFactor.objects.create(from_currency=self.krw, to_currency=self.aud, factor=0.95, date=timezone.now())

    def test_with_string(self):
        path, factor, amount = self.eur.convert_to("USD")
        self.assertEqual(path, [self.eur, self.usd])
        self.assertAlmostEqual(factor, Decimal(1.2))
        self.assertAlmostEqual(amount, Decimal(1.2))

    def test_with_invalid_string(self):
        path, factor, amount = self.eur.convert_to("XYZ")
        self.assertIsNone(path)
        self.assertIsNone(factor)
        self.assertAlmostEqual(amount, Decimal(1))

    def test_direct_conversion(self):
        path, factor, amount = self.eur.convert_to(self.usd)
        self.assertEqual(path, [self.eur, self.usd])
        self.assertAlmostEqual(factor, Decimal(1.2))
        self.assertAlmostEqual(amount, Decimal(1.2))

    def test_reversed_conversion(self):
        path, factor, amount = self.usd.convert_to(self.eur)
        self.assertEqual(path, [self.usd, self.eur])
        self.assertAlmostEqual(factor, Decimal(1 / 1.2))
        self.assertAlmostEqual(amount, Decimal(1 / 1.2))

    def test_direct_conversion_with_amount(self):
        path, factor, amount = self.eur.convert_to(self.usd, amount=12)
        self.assertEqual(path, [self.eur, self.usd])
        self.assertAlmostEqual(factor, Decimal(1.2))
        self.assertAlmostEqual(amount, Decimal(12 * 1.2))

    def test_reversed_conversion_with_amount(self):
        path, factor, amount = self.usd.convert_to(self.eur, amount=12)
        self.assertEqual(path, [self.usd, self.eur])
        self.assertAlmostEqual(factor, Decimal(1 / 1.2))
        self.assertAlmostEqual(amount, Decimal(12 * 1 / 1.2))

    def test_indirect_path(self):
        path, factor, amount = self.gbp.convert_to(self.usd)
        self.assertEqual(path, [self.gbp, self.eur, self.usd])
        self.assertAlmostEqual(factor, Decimal(1.1 * 1.2))
        self.assertAlmostEqual(amount, Decimal(1.1 * 1.2))

    def test_reversed_indirect_path(self):
        path, factor, amount = self.usd.convert_to(self.gbp)
        self.assertEqual(path, [self.usd, self.eur, self.gbp])
        self.assertAlmostEqual(factor, Decimal((1 / 1.2) * (1 / 1.1)))
        self.assertAlmostEqual(amount, Decimal((1 / 1.2) * (1 / 1.1)))

    def test_long_conversion_chain(self):
        path, factor, amount = self.usd.convert_to(self.aud)
        expected_path = [self.usd, self.eur, self.inr, self.cny, self.jpy, self.krw, self.aud]
        self.assertEqual(path, expected_path)
        expected_factor = Decimal(1 / 1.2 * 88 * 0.12 * 17 * 10 * 0.95)
        self.assertAlmostEqual(factor, expected_factor, places=4)
        self.assertAlmostEqual(amount, expected_factor, places=4)

    def test_path_not_found(self):
        path, factor, amount = self.usd.convert_to(self.zzz)
        self.assertIsNone(path)
        self.assertIsNone(factor)
        self.assertAlmostEqual(amount, Decimal(1))

    def test_cycle_resilience(self):
        # Create a loop (EUR → USD already exists)
        ConversionFactor.objects.create(from_currency=self.jpy, to_currency=self.usd, factor=0.009, date=timezone.now())

        # Validate that the loop doesn’t affect correct output
        path, factor, amount = self.usd.convert_to(self.jpy)
        expected_path = [self.usd, self.jpy]
        self.assertEqual(path, expected_path)


class ConversionFactorModelTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_base_currency=True)
        self.eur = Currency.objects.create(code="EUR", name="Euro", symbol="€")
        self.eur_to_usd = ConversionFactor.objects.create(from_currency=self.eur, to_currency=self.usd, factor=1, date=timezone.now())

    def test_str(self):
        self.assertEqual(str(self.eur_to_usd), f"EUR:USD 1 ({timezone.now().date().isoformat()})")

    def test_save_no_date(self):
        usd_to_eur = ConversionFactor.objects.create(from_currency=self.usd, to_currency=self.eur, factor=1)
        self.assertEqual(usd_to_eur.date.date(), timezone.now().date())
