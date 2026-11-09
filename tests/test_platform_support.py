import os
from pathlib import Path
import unittest
from unittest.mock import patch

import platform_support as platform
import ki


class PlatformTests(unittest.TestCase):
    def test_mac_data_outside_checkout(self):
        with patch.object(platform, "IS_MAC", True), patch.object(platform.sys, "platform", "darwin"), patch.object(Path, "home", return_value=Path("/example/user")):
            self.assertEqual(platform.data_dir(), Path("/example/user/Library/Application Support/WISP"))

    def test_windows_data(self):
        with patch.object(platform.sys, "platform", "win32"), patch.dict(os.environ, {"APPDATA": "example-data"}):
            self.assertEqual(platform.data_dir(), Path("example-data/WISP"))

    def test_key_newline_rejected_before_file_access(self):
        with self.assertRaises(ValueError):
            ki.speichere_schluessel("GROQ_API_KEY", "dummy\nOPENROUTER_API_KEY=injected")

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            ki.speichere_schluessel("OTHER", "dummy")


if __name__ == "__main__":
    unittest.main()
