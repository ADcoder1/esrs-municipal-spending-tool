import tempfile
import unittest
from pathlib import Path

from esrs_tool import config


class ConfigTests(unittest.TestCase):
    def test_local_config_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.local.json"
            payload = {
                "invoice_path": "/tmp/invoices.xlsx",
                "mapping_path": "/tmp/mapping.xlsx",
                "meeting_notes_path": "",
            }
            config.save_local_config(payload, path)
            loaded = config.load_local_config(path)
            self.assertEqual(
                loaded,
                {
                    "invoice_path": "/tmp/invoices.xlsx",
                    "mapping_path": "/tmp/mapping.xlsx",
                },
            )


if __name__ == "__main__":
    unittest.main()
