"""Approval lock, implicit defaults and backwards-compatible explicit loading."""
import importlib.util
import json
from pathlib import Path
import unittest

from dancerudiments_authoring.collections import initial_pack
try:
    import dancerudiments as d
except ImportError:
    d = None
ROOT = Path(__file__).resolve().parents[2]

class ApprovalTests(unittest.TestCase):
    def test_checked_registration_matches_approval(self):
        spec=importlib.util.spec_from_file_location('defaults_builder',ROOT/'tools/build_default_catalogue.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.build(check=True)
        lock=json.loads((ROOT/'collections/defaults.json').read_text())
        self.assertEqual(lock['collections'][0]['patterns'],[p.name for p in initial_pack().patterns])

@unittest.skipIf(d is None,'Native extension unavailable')
class DefaultTests(unittest.TestCase):
    def test_all_defaults_available_without_pack_loading(self):
        names=[p['name'] for p in d.catalogue()]
        self.assertEqual(len(names),787);self.assertEqual(len(names),len(set(names)))
        for p in initial_pack().patterns:
            self.assertIn(p.name,names)
            self.assertEqual(d.sample(p.name,-1).as_tuple(),p.samples[-1])

    def test_exact_reloads_are_idempotent(self):
        self.assertEqual(initial_pack().to_native().catalogue(),d.catalogue())
        self.assertEqual(initial_pack(['lfo_breathe']).to_native().catalogue(),d.catalogue())

    def test_altered_default_samples_are_rejected(self):
        p=initial_pack(['lfo_breathe']).patterns[0]
        rows=[list(v) for v in p.samples];rows[20][0]=.123
        changed=d.SampledPattern(p.name,p.description,rows)
        with self.assertRaisesRegex(ValueError,'override'):d.PatternLibrary([changed])
        self.assertEqual(d.sample(p.name,20).as_tuple(),p.samples[20])

    def test_altered_default_metadata_is_rejected(self):
        p=initial_pack(['lfo_breathe']).patterns[0]
        changed=d.SampledPattern(p.name,'Edited description',p.samples)
        with self.assertRaisesRegex(ValueError,'override'):d.PatternLibrary([changed])
        with self.assertRaisesRegex(ValueError,'Duplicate'):d.PatternLibrary([p.to_native(),p.to_native()])
