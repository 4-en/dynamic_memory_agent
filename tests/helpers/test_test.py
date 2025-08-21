from dma.utils.test_util import add
import unittest

class TestUtil(unittest.TestCase):
    def setUp(self):
        # fresh state per test
        self.numbers = [(1, 2, 3), (0, 0, 0), (-1, 1, 0)]

    def test_add_table(self):
        for a, b, expected in self.numbers:
            with self.subTest(a=a, b=b):
                self.assertEqual(add(a, b), expected)


