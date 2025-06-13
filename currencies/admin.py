from django.contrib import admin

from .models import Currency, ConversionRate

admin.site.register(Currency)
admin.site.register(ConversionRate)
