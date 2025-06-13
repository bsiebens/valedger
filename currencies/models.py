from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class Currency(models.Model):
    code = models.CharField(_("code"), max_length=3, unique=True)
    name = models.CharField(_("name"), max_length=100)
    symbol = models.CharField(_("symbol"), max_length=10, blank=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = _("currency")
        verbose_name_plural = _("currencies")

    def convert(self, to_currency: str, amount: float | Decimal = Decimal("1.0")) -> Decimal:
        """Converts to a given currency, optionally specifiying an amount to convert. Returns the amount if no rate exists."""

        amount = Decimal(amount)

        try:
            conversion_rate = self.conversionrates_from.filter(to_currency__code=to_currency).latest()
            return amount * conversion_rate.factor

        except ConversionRate.DoesNotExist:
            return amount


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
        unique_together = ["from_currency", "to_currency", "date"]  # Only allow 1 rate per day
