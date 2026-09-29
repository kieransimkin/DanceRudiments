"""Compact release snapshots retain independently checkable native table hashes."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('compact_release_demo', ROOT/'tools/release_demo.py')
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


class CompactReleaseDemoTests(unittest.TestCase):
    def build(self, samples):
        pattern = dict(name='fixture', description='Test fixture', period_pips=len(samples),
                       samples=samples, provenance={}, diagnostics={}, source_sha256='0'*64)
        def compiler(command, **kwargs):
            # Unit-test serialization without a build-tool dependency. Actual
            # Clang/WASM output is exercised by the separate browser renderer.
            Path(command[-1]).write_bytes(b'\x00asm\x01\x00\x00\x00')
        with tempfile.TemporaryDirectory() as folder, patch.object(module.subprocess, 'run', compiler):
            path = module.build_page([pattern], '0.1.3-test', 'fixture', folder, native=False)
            html = path.read_text()
            payload = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
            return payload, json.loads(path.with_suffix('.json').read_text())

    def test_no_duplicate_decimal_table(self):
        payload, manifest = self.build([[0, .25, -.5], [.75, -.25, 1]])
        self.assertEqual(payload['pack']['schema_version'], 2)
        self.assertNotIn('samples', payload['pack']['patterns'][0])
        self.assertEqual(manifest['sample_count'], 2)
        self.assertTrue(payload['wasm'])

    def test_hash_represents_native_values(self):
        samples = [[0, .25, -.5], [.75, -.25, 1]]
        payload, manifest = self.build(samples)
        expected = sha256(b''.join(struct.pack('<ddd', *row) for row in samples)).hexdigest()
        self.assertEqual(manifest['sample_hashes'], [expected])
        self.assertEqual(payload['pack']['patterns'][0]['samples_f64le_sha256'], expected)

    def test_signed_zero_matches_numeric_comparison(self):
        a, ma = self.build([[-0.0, 0, -0.0]])
        b, mb = self.build([[0.0, 0, 0.0]])
        self.assertEqual(ma['sample_hashes'], mb['sample_hashes'])

    def test_changed_native_value_changes_reference(self):
        _, a = self.build([[0, .25, -.5]])
        _, b = self.build([[0, .25, -.500001]])
        self.assertNotEqual(a['sample_hashes'], b['sample_hashes'])
        self.assertNotEqual(a['pack_sha256'], b['pack_sha256'])

    def test_invalid_tables_fail_before_compilation(self):
        for samples in ([[2, 0, 0]], [[float('nan'), 0, 0]], [[0, 0]]):
            with self.assertRaises(ValueError):
                module.validate([dict(name='bad', period_pips=1, samples=samples)])
