from collections import defaultdict, deque
from decimal import Decimal

from django.db import models
from django.db.models import Max
from django.utils import timezone
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
        """
        Ensure that there is always one base currency. If this currency is being set as base, unset others. If no other base currency exists, this one becomes base.
        """
        if self.is_base_currency:
            Currency.objects.exclude(pk=self.pk).update(is_base_currency=False)
        elif not Currency.objects.exclude(pk=self.pk).filter(is_base_currency=True).exists():
            # No other base currency exists, so this one must be base.
            self.is_base_currency = True

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # If this is the base currency being deleted, try to assign another one as base.
        if self.is_base_currency:
            # Check if there are other currencies to promote
            other_currencies = Currency.objects.exclude(pk=self.pk)
            if other_currencies.exists():
                new_base_currency = other_currencies.first()
                new_base_currency.is_base_currency = True
                new_base_currency.save()
            # If no other currencies, no action needed here; the last base is simply deleted.

        return super().delete(*args, **kwargs)

    def convert_to(self, to_currency: "str | Currency", amount: float | Decimal = Decimal("1.0")) -> Decimal:
        if not isinstance(amount, Decimal):
            amount = Decimal(amount)

        if not isinstance(to_currency, Currency):
            try:
                to_currency = Currency.objects.get(code=to_currency)

            except Currency.DoesNotExist:
                return None, None, amount

        graph = defaultdict(list)
        conversion_factor_lookup = {}

        # Step 1: find the latest date for each (from, to) pair
        latest_dates = ConversionFactor.objects.values("from_currency", "to_currency").annotate(latest_date=Max("date"))

        # Step 2: fetch the most recent conversion factors
        for entry in latest_dates:
            from_curr = entry["from_currency"]
            to_curr = entry["to_currency"]
            latest = entry["latest_date"]

            conversion_factor = ConversionFactor.objects.get(from_currency=from_curr, to_currency=to_curr, date=latest)

            graph[conversion_factor.from_currency].append(conversion_factor.to_currency)
            conversion_factor_lookup[(conversion_factor.from_currency, conversion_factor.to_currency)] = conversion_factor.factor

            # Add reverse edge
            graph[conversion_factor.to_currency].append(conversion_factor.from_currency)
            conversion_factor_lookup[(conversion_factor.to_currency, conversion_factor.from_currency)] = Decimal("1.0") / conversion_factor.factor

        # Step 3: breadth-first search (BFS)
        queue = deque([(self, [self], Decimal("1.0"))])
        visited = set()

        while queue:
            current, path, factor = queue.popleft()
            if current == to_currency:
                return path, factor, amount * factor

            visited.add(current)

            for neighbor in graph[current]:
                if neighbor not in visited:
                    new_factor = factor * conversion_factor_lookup[(current, neighbor)]
                    queue.append((neighbor, path + [neighbor], new_factor))

        return None, None, amount


class ConversionFactor(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="conversionfactors_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="conversionfactors_to")

    factor = models.DecimalField(_("factor"), max_digits=10, decimal_places=4)
    date = models.DateField(_("date"), default=timezone.now)

    def __str__(self):
        return f"{self.from_currency.code}:{self.to_currency.code} {self.factor} ({self.date.date().isoformat()})"

    class Meta:
        verbose_name = _("conversion rate")
        verbose_name_plural = _("conversion rates")
        get_latest_by = "date"
        ordering = ["-date"]
        unique_together = ("from_currency", "to_currency", "date")
