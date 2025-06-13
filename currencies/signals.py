from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal

from .models import ConversionRate


@receiver(post_save, sender=ConversionRate)
def create_or_update_reverse_conversion_rate(instance: ConversionRate, *args, **kwargs) -> None:
    if instance.factor == Decimal("0.0"):
        reverse_factor = Decimal("0.0")
    else:
        reverse_factor = Decimal("1.0") / instance.factor

    # If a reverse rate with the exact target factor already exists, do nothing to prevent loops or unnecessary updates.
    if not ConversionRate.objects.filter(from_currency=instance.to_currency, to_currency=instance.from_currency, date=instance.date, factor=reverse_factor).exists():
        ConversionRate.objects.update_or_create(
            from_currency=instance.to_currency, to_currency=instance.from_currency, date=instance.date, defaults={"factor": reverse_factor}
        )


@receiver(post_delete, sender=ConversionRate)
def delete_reverse_conversion_rate(instance: ConversionRate, *args, **kwargs) -> None:
    try:
        ConversionRate.objects.get(from_currency=instance.to_currency, to_currency=instance.from_currency, date=instance.date).delete()

    except ConversionRate.DoesNotExist:
        pass
