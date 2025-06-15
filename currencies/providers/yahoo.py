from decimal import Decimal

import yfinance as yf

from ..models import ConversionFactor, Currency


def download_conversion_rates(currencies: list[str], base_currency: str, period: str = "7d") -> None:
    try:
        currencies = [currency for currency in Currency.objects.filter(code__in=currencies)]
        base_currency = Currency.objects.get(code=base_currency)

    except Currency.DoesNotExist:
        pass

    currencies_cache = {}
    for currency in currencies:
        try:
            last_conversion_factor = currency.conversionfactors_from.filter(to_currency__code=base_currency).latest()
            currencies_cache[currency.code] = last_conversion_factor.date

        except ConversionFactor.DoesNotExist:
            currencies_cache[currency.code] = None

    # Download data from yahoo
    tickers = [f"{currency.code}{base_currency.code}=X" for currency in currencies]
    ticker_data = yf.download(tickers, period=period, progress=False)

    conversion_factors = []

    for index, row in ticker_data.iterrows():
        for currency in currencies:
            if currencies_cache[currency.code] is None or index.date() > currencies_cache[currency.code]:
                conversion_factor = Decimal(row[("Close", f"{currency.code}{base_currency.code}=X")])
                reverse_conversion_factor = Decimal("1.0") / conversion_factor

                conversion_factors.append(ConversionFactor(from_currency=currency, to_currency=base_currency, date=index.date(), factor=conversion_factor))
                conversion_factors.append(ConversionFactor(from_currency=base_currency, to_currency=currency, date=index.date(), factor=reverse_conversion_factor))
                currencies_cache[currency.code] = index.date()

    ConversionFactor.objects.bulk_create(conversion_factors)
