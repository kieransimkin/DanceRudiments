"""Strict artifact integrity vs. cross-platform numerical recipe verification."""
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dancerudiments_authoring import compile_pack, emit_json
from dancerudiments_authoring._validation import canonical_json
from dancerudiments_authoring._reproducibility import (
    ENVIRONMENT_VARIABLE, PORTABLE_ABS_TOL, assert_rebuild_equal,
    checked_compiled_pack, checked_score, portable_checks,
)
from dancerudiments_authoring.model import CompiledPack

ROOT = Path(__file__).resolve().parents[2]


class ReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {ENVIRONMENT_VARIABLE: 'portable'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_exact_mode_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(portable_checks())
            with self.assertRaisesRegex(ValueError, 'absolute difference'):
                assert_rebuild_equal(0.5, math.nextafter(0.5, 1.0))

    def test_explicit_exact_rejects_last_decimal_drift(self):
        with patch.dict(os.environ, {ENVIRONMENT_VARIABLE: 'exact'}):
            with self.assertRaises(ValueError):
                assert_rebuild_equal([0.481645548966], [0.481645548965])

    def test_portable_accepts_last_decimal_drift(self):
        assert_rebuild_equal([0.481645548966], [0.481645548965])

    def test_portable_rejects_material_float_change(self):
        with self.assertRaisesRegex(ValueError, r'\$\.samples\[0\]'):
            assert_rebuild_equal({'samples': [0.5+4*PORTABLE_ABS_TOL]}, {'samples': [0.5]})

    def test_no_relative_tolerance_for_large_values(self):
        with self.assertRaises(ValueError):
            assert_rebuild_equal(1e6 + 1e-5, 1e6)

    def test_nan_and_infinity_are_never_equal(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assert_rebuild_equal(value, value)

    def test_integer_counts_remain_exact(self):
        for candidate in (65, 64.0, True):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                assert_rebuild_equal({'period_pips': candidate}, {'period_pips': 64})

    def test_rational_event_times_remain_exact(self):
        with self.assertRaises(ValueError):
            assert_rebuild_equal({'beat': '1/3'}, {'beat': '0.333333333333'})

    def test_metadata_and_digest_fields_remain_exact(self):
        for key in ('name', 'source_sha256', 'license', 'bounds'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                assert_rebuild_equal({key: 'changed'}, {key: 'original'})

    def test_order_and_keys_and_array_size_remain_exact(self):
        for actual, expected in ((['x','y'], ['y','x']), ({'x':1}, {'y':1}), ([1,2], [1])):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                assert_rebuild_equal(actual, expected)

    def test_bad_mode_fails_closed(self):
        with patch.dict(os.environ, {ENVIRONMENT_VARIABLE: 'portble'}):
            with self.assertRaisesRegex(ValueError, 'must be exact or portable'):
                portable_checks()

    def fixture(self, root):
        score = {'format': 'dancerudiments.score-pack', 'schema_version': 1,
                 'patterns': [{'name': 'ci_fixture', 'period_beats': 1,
                     'tracks': [{'axis':'x', 'curve':{'type':'lfo', 'shape':'sine', 'gain':0.5}}]}]}
        pack = compile_pack(score)
        score_path = root/'collections/tiny/tiny.score.json'
        pack_path = root/'python/dancerudiments_authoring/packs/tiny.json'
        for p in (score_path, pack_path):
            p.parent.mkdir(parents=True, exist_ok=True)
        score_path.write_text(json.dumps(score), encoding='utf-8')
        pack_path.write_text(emit_json(pack), encoding='utf-8')
        lock = {'format':'dancerudiments.default-selection', 'schema_version':2,
            'collections':[{'id':'tiny', 'pack':pack_path.relative_to(root).as_posix(),
                            'pack_sha256':sha256(canonical_json(pack.to_dict()).encode()).hexdigest()}]}
        (root/'collections/defaults.json').write_text(json.dumps(lock), encoding='utf-8')
        return score, pack, pack_path

    def test_portable_score_verifies_before_returning_frozen_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); score, pack, _ = self.fixture(root)
            changed=deepcopy(score)
            changed['patterns'][0]['tracks'][0]['curve']['gain'] += 1e-12
            original_bytes={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            saved, result=checked_score(changed, root, 'tiny', True)
            self.assertEqual(saved, score)
            self.assertEqual(result.to_dict(), pack.to_dict())
            self.assertEqual(original_bytes, {p:p.read_bytes() for p in original_bytes})

    def test_portable_rejects_changed_recipe(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); score, _, _ = self.fixture(root)
            score['patterns'][0]['tracks'][0]['curve']['gain'] += .01
            with self.assertRaisesRegex(ValueError, 'tiny.recipe'):
                checked_score(score, root, 'tiny', True)

    def test_direct_pack_verification_uses_same_tolerance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); _, pack, _ = self.fixture(root)
            changed=pack.to_dict()
            changed['patterns'][0]['samples'][1][0] += 1e-12
            result=checked_compiled_pack(CompiledPack.from_dict(changed), root, 'tiny', True)
            self.assertEqual(result.to_dict(), pack.to_dict())
            changed['patterns'][0]['samples'][1][0] += .001
            with self.assertRaises(ValueError):
                checked_compiled_pack(CompiledPack.from_dict(changed), root, 'tiny', True)

    def test_even_sub_tolerance_pack_tampering_fails_hash_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); score, pack, path = self.fixture(root)
            changed=pack.to_dict();changed['patterns'][0]['samples'][1][0] += 1e-12
            path.write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA-256 lock'):
                checked_score(score, root, 'tiny', True)

    def test_portable_write_mode_does_not_reuse_saved_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); score, old, _ = self.fixture(root)
            score['patterns'][0]['tracks'][0]['curve']['gain'] = .8
            saved, new = checked_score(score, root, 'tiny', False)
            self.assertEqual(saved, score)
            self.assertNotEqual(new.to_dict(), old.to_dict())

    def test_all_multicommand_matrix_steps_use_fail_fast_bash(self):
        # Guard the cross-platform job's explicit shell policy, not the installed
        # shell's behavior; the Windows runner exercises the latter in CI.
        workflow=(ROOT/'.github/workflows/patterns.yml').read_text(encoding='utf-8')
        job=workflow.split('  authoring-and-native:',1)[1].split('  real-wasm:',1)[0]
        self.assertIn('    defaults:\n      run:',job)
        self.assertIn('        shell: bash',job)
        self.assertIn("matrix.os == 'ubuntu-latest' && matrix.python == '3.13' && 'exact' || 'portable'",job)
        self.assertNotIn('continue-on-error',job)
