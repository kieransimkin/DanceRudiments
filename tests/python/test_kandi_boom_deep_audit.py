"""Source-level safety, geometry, bind-pose and fixture regression tests."""

import hashlib
import importlib.util
import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from kandi_boom_fbx import FbxArray, parse_fbx, inspect_fbx, _matmul_error  # noqa: E402


class KandiBoomDeepAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = ROOT / 'harness/kandi-boom/assets'
        cls.audit = json.loads((ROOT / 'harness/kandi-boom/rig-audit.json').read_text(encoding='utf-8'))
        cls.pose = json.loads((ROOT / 'harness/kandi-boom/source-rig.json').read_text(encoding='utf-8'))

    def test_geometry_and_uv_topology(self):
        geometry = self.audit['deep_validation']['mesh']
        self.assertEqual(geometry['control_point_count'], 14950)
        self.assertEqual(geometry['triangle_count'], 29965)
        self.assertTrue(geometry['triangle_only'])
        self.assertEqual(geometry['normal_count'], geometry['polygon_corner_count'])
        self.assertEqual(geometry['uv_index_count'], geometry['polygon_corner_count'])
        self.assertEqual(geometry['uv_mapping'], 'ByPolygonVertex')
        self.assertLess(geometry['max_normal_length_deviation'], 0.005)
        self.assertEqual(geometry['bounds_xyz_in_fbx_units'][1], [0.0, 172.0])
        for f in ('albedo.png', 'normal.png', 'roughness.png', 'metallic.png'):
            img = self.audit['assets'][f]['png']
            self.assertEqual((img['width'], img['height']), (2048, 2048))
            self.assertTrue(img['png_chunk_crcs_valid'])

    def test_skin_and_bind_matrices(self):
        skin = self.audit['deep_validation']['skin']
        bind = self.audit['deep_validation']['bind_pose']
        self.assertEqual(skin['vertex_count'], 14950)
        self.assertEqual(skin['unweighted_vertex_count'], 0)
        self.assertEqual(skin['cluster_count'], len(self.pose['bones']))
        self.assertEqual(skin['zero_influence_bones'], ['head_end', 'headfront'])
        self.assertLess(skin['maximum_weight_sum_error'], 0.0001)
        self.assertLess(bind['max_cluster_link_pose_error'], 1e-5)
        self.assertLess(bind['max_inverse_bind_identity_error'], 0.0002)
        self.assertEqual(bind['pose_matrix_count'], 26)
        self.assertEqual(skin['vertices_with_over_four_influences'], 1071)
        self.assertGreater(skin['max_discarded_weight_if_four_influences'], 0.2)
        self.assertFalse(self.audit['deep_validation']['production_four_influence_ready'])
        for bone in self.pose['bones']:
            self.assertLess(_matmul_error(bone['inverse_bind_matrix'], bone['world_bind_matrix']), 0.0002)

    def test_matrix_residual_is_stable_across_supported_python_versions(self):
        # Python 3.12 changed float sum() accuracy. The audit must not depend on
        # which supported interpreter evaluates the same four matrix products.
        bone = next(b for b in self.pose['bones'] if b['name'] == 'head_end')
        self.assertEqual(
            _matmul_error(bone['inverse_bind_matrix'], bone['world_bind_matrix']),
            self.audit['deep_validation']['bind_pose']['max_inverse_bind_identity_error'],
        )

    def test_source_has_no_recorded_motion_and_is_not_rigify(self):
        animation = self.audit['deep_validation']['animation']
        self.assertEqual(animation['stack_count'], 1)
        self.assertEqual(animation['curve_count'], 225)
        self.assertEqual(animation['curve_key_count_histogram'], {'1': 225})
        self.assertFalse(animation['contains_recorded_motion'])
        self.assertEqual(self.pose['channel_mapping_status'], 'unmapped')
        self.assertEqual(self.pose['type_uri'], 'syn://type/danceflow/motion/rig/custom/kandi-boom')
        self.assertIsNone(self.audit['rigify_compatible'])

    def test_manifest_fingerprint_is_reproducible(self):
        raw = (self.assets / 'kandi-boom.fbx').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        report, pose = inspect_fbx(raw, digest)
        self.assertEqual(report, self.audit['deep_validation'])
        self.assertEqual(pose, self.pose)
        self.assertEqual(digest, self.pose['fbx_asset_sha256'])
        self.assertEqual(set(b['name'] for b in pose['bones']), set(b['name'] for b in self.audit['bones']))

    def test_checked_in_audit_cli_check_mode(self):
        proc = subprocess.run([sys.executable, 'tools/audit_kandi_boom.py',
                               '--output', 'harness/kandi-boom/rig-audit.json',
                               '--source-rig-output', 'harness/kandi-boom/source-rig.json',
                               '--check'], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_rejects_truncated_fbx_and_zip_bomb(self):
        with self.assertRaisesRegex(ValueError, 'FBX'):
            parse_fbx(b'Kaydara FBX Binary  \x00\x1a\x00' + b'garbled')
        large_payload = zlib.compress(b'0' * 100)
        with self.assertRaisesRegex(ValueError, 'overlong|invalid'):
            FbxArray('i', 1, large_payload, 1).values()
        with self.assertRaisesRegex(ValueError, 'decoded size'):
            FbxArray('d', 9_000_000, b'', 1).values()

    def test_rejects_png_crc_errors(self):
        # Corrupt only the critical IHDR CRC on a copy; leave original immutable.
        with tempfile.TemporaryDirectory() as tmp:
            candidate = pathlib.Path(tmp) / 'bad.png'
            raw = bytearray((self.assets / 'normal.png').read_bytes())
            raw[29] ^= 0x01
            candidate.write_bytes(raw)
            from audit_kandi_boom import _inspect_png
            with self.assertRaisesRegex(ValueError, 'CRC'):
                _inspect_png(candidate)


if __name__ == '__main__':
    unittest.main()
