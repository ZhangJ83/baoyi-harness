import os
import tempfile
import unittest
from unittest.mock import patch

from agent.doctor import report


class DoctorTests(unittest.TestCase):
    def test_report_never_contains_key_value(self):
        secret = "sk-doctor-secret-value"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp, "OPENAI_API_KEY": secret, "PROVIDER": "openai"}, clear=False):
            result = report()
        self.assertTrue(result["api_key_configured"])
        self.assertEqual(result["api_key_length"], len(secret))
        self.assertNotIn(secret, str(result))


if __name__ == "__main__":
    unittest.main()
