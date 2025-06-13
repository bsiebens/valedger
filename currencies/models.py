from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class Currency(models.Model):
    code = models.CharField(_("code"), max_length=3, unique=True)
    name = models.CharField(_("name"), max_length=100)
    symbol = models.CharField(_("symbol"), max_length=10, blank=True)

    is_base_currency = models.BooleanField(_("base currency"), default=False)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = _("currency")
        verbose_name_plural = _("currencies")

    def save(self, *args, **kwargs):
        if not Currency.objects.exclude(pk=self.pk).filter(is_base_currency=True).exists():
            # No other base currency exists, set this as base if not already
            self.is_base_currency = True
        elif self.is_base_currency:
            # If this is being set as base, unset all others
            Currency.objects.exclude(pk=self.pk).update(is_base_currency=False)

        super().save(*args, **kwargs)

    def convert(self, to_currency: "str | Currency", amount: float | Decimal = Decimal("1.0")) -> Decimal:
        """Converts to a given currency, optionally specifiying an amount to convert. Returns the amount if no rate exists."""

        amount = Decimal(amount)

        if not isinstance(to_currency, Currency):
            to_currency = Currency.objects.get(code=to_currency)

        if to_currency == self:
            return amount

        if self.is_base_currency or to_currency.is_base_currency:
            try:
                conversion_rate = self.conversionrates_from.filter(to_currency=to_currency).latest()
                return amount * conversion_rate.factor

            except ConversionRate.DoesNotExist:
                return amount

        else:
            base_currency = Currency.objects.get(is_base_currency=True)

            try:
                currency_to_base_currency_conversion = self.conversionrates_from.filter(to_currency=base_currency).latest()
                base_currency_to_to_currency_conversion = base_currency.conversionrates_from.filter(to_currency=to_currency).latest()

                return amount * currency_to_base_currency_conversion.factor * base_currency_to_to_currency_conversion.factor

            except ConversionRate.DoesNotExist:
                return amount

    def download_historical_rates(self): ...


class ConversionRate(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="conversionrates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="conversionrates_to")

    factor = models.DecimalField(_("factor"), max_digits=10, decimal_places=4)
    date = models.DateField(_("date"))

    def __str__(self):
        return f"{self.from_currency.code}:{self.to_currency.code} {self.factor} ({self.date.isoformat()})"

    class Meta:
        verbose_name = _("conversion rate")
        verbose_name_plural = _("conversion rates")
        get_latest_by = "date"
        ordering = ["-date"]
