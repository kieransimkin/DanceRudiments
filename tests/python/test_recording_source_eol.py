"""Exact WASM source identities must survive Windows-style Git checkouts."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('tools/recording_wasm.cpp', 'include/dancerudiments/recording_view.hpp')


class RecordingSourceEolTests(unittest.TestCase):
    def test_hashed_recording_sources_survive_autocrlf_checkout(self):
        manifest = json.loads((ROOT / 'python/dancerudiments_authoring/harness_assets/recording.wasm.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            for relative in SOURCES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout
            git('init', '-q')
            git('config', 'core.autocrlf', 'true')
            git('add', '--', '.gitattributes', *SOURCES)
            for relative in SOURCES:
                (root / relative).unlink()
            git('checkout-index', '--all', '--force')
            for relative in SOURCES:
                self.assertIn('eol: lf', git('check-attr', 'eol', '--', relative))
                raw = (root / relative).read_bytes()
                self.assertNotIn(b'\r\n', raw)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest[relative], relative)


if __name__ == '__main__':
    unittest.main()
