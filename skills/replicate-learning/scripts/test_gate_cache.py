"""The snapshot cache must never reuse lines from another revision."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_all
import gate_lecture


class SnapshotCacheTests(unittest.TestCase):
    def test_reset_for_new_sha_clears_file_cache(self):
        gate_lecture._snap_file_cache["module/file.py"] = ["old revision"]
        with patch.object(gate_lecture, "load_snapshot", return_value=True):
            gate_all.reset_snap("newsha")
        self.assertEqual(gate_lecture._snap_file_cache, {})


if __name__ == "__main__":
    unittest.main()
