import unittest
from unittest.mock import Mock, patch

def add(a, b):
    """Simple function to add two numbers."""
    return a + b

def fetch_user(api, user_id):
    """Fetch user data from an API."""
    return api.get_user(user_id)

class TestCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # expensive setup shared by all tests in this class
        pass

    def setUp(self):
        # fresh state per test
        self.numbers = [(1, 2, 3), (0, 0, 0), (-1, 1, 0)]

    def test_add_table(self):
        for a, b, expected in self.numbers:
            with self.subTest(a=a, b=b):
                self.assertEqual(add(a, b), expected)

"""     def test_fetch_user_with_mock(self):
        api = Mock()
        api.get_user.return_value = {"id": "42", "name": "Ada"}
        self.assertEqual(fetch_user(api, "42")["name"], "Ada")
        api.get_user.assert_called_once_with("42")

    @patch("mypackage.core.fetch_user")  # patch by import path
    def test_patch_example(self, mock_fetch):
        mock_fetch.return_value = {"id": "1", "name": "Pat"}
        self.assertEqual(fetch_user(Mock(), "1")["name"], "Pat") """
