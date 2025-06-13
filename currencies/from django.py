from django.test import TestCase
from .tests import CurrencyModelTests, ConversionRateModelTests, ConversionRateSignalTests

# Python

class TestCurrencyModelTests(TestCase):
    def test_all_methods_run(self):
        test_case = CurrencyModelTests(methodName='test_currency_str')
        test_case.setUp()
        for method in dir(CurrencyModelTests):
            if method.startswith('test_'):
                with self.subTest(method=method):
                    getattr(test_case, method)()

class TestConversionRateModelTests(TestCase):
    def test_all_methods_run(self):
        test_case = ConversionRateModelTests(methodName='test_conversion_rate_str')
        test_case.setUp()
        for method in dir(ConversionRateModelTests):
            if method.startswith('test_'):
                with self.subTest(method=method):
                    getattr(test_case, method)()

class TestConversionRateSignalTests(TestCase):
    def test_all_methods_run(self):
        test_case = ConversionRateSignalTests(methodName='test_reverse_rate_created_on_new_save')
        test_case.setUp()
        for method in dir(ConversionRateSignalTests):
            if method.startswith('test_'):
                with self.subTest(method=method):
                    getattr(test_case, method)()