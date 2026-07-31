import os
import unittest
from unittest.mock import patch

from m18_api import M18Client
from services.business_config import load_business_config


class EnvironmentConfigTests(unittest.TestCase):
    def test_client_rejects_missing_selected_environment(self):
        with patch.dict(os.environ, {"M18_ENV": "missing-test-environment"}, clear=False):
            with self.assertRaisesRegex(FileNotFoundError, "missing-test-environment"):
                M18Client()

    def test_business_config_rejects_missing_selected_environment(self):
        with patch.dict(os.environ, {"M18_ENV": "missing-test-environment"}, clear=False):
            with self.assertRaisesRegex(FileNotFoundError, "missing-test-environment"):
                load_business_config()


if __name__ == "__main__":
    unittest.main()
