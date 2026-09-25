"""Cache reuse and transcript invalidation."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_cache import get_or_build


class FileCacheTests(unittest.TestCase):
    def test_reuses_unchanged_file_and_rebuilds_after_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "transcript.jsonl"
            source.write_text("first\n")
            calls = []

            def build():
                calls.append(1)
                return {"redacted": source.read_text()}

            with mock.patch.dict(os.environ, {"RECALL_CACHE_DIR": str(root / "cache")}):
                first = get_or_build(source, "codex", 1, build)
                self.assertEqual(first, get_or_build(source, "codex", 1, build))
                self.assertEqual(len(calls), 1)
                source.write_text("second version\n")
                second = get_or_build(source, "codex", 1, build)
                self.assertEqual(len(calls), 2)
                self.assertNotEqual(first, second)
                cache = next((root / "cache" / "codex").glob("*.json"))
                self.assertEqual(cache.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
