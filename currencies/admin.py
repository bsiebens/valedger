from django.contrib import admin

from .models import Currency, ConversionFactor

admin.site.register(Currency)
admin.site.register(ConversionFactor)
