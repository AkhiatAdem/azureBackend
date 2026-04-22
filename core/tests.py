from django.test import TestCase

from django.test import TestCase

class BasicTest(TestCase):
    def test_environment_is_sane(self):
        self.assertEqual(1 + 1, 2)
