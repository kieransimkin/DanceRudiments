"""Character source validation without importing optional rendering dependencies."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('audit_kandi_boom', ROOT / 'tools/audit_kandi_boom.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class KandiBoomAuditTests(unittest.TestCase):
    def test_checked_in_fbx_and_maps(self):
        assets = ROOT / 'harness/kandi-boom/assets'
        if not assets.exists():
            self.fail('Kandi Boom asset directory missing')
        result = AUDIT.inspect(assets)
        self.assertEqual(result['fbx_version'], 7400)
        self.assertGreater(result['bone_count'], 0)
        self.assertGreater(result['mesh_count'], 0)
        self.assertGreater(result['cluster_count'], 0)
        self.assertEqual(result['motion_mapping_status'], 'unmapped')
        baseline = json.loads((ROOT / 'harness/kandi-boom/rig-audit.json').read_text(encoding='utf-8'))
        self.assertEqual(result, baseline, 'model/texture assets or rig hierarchy differ from approved audit')
        self.assertTrue(all(len(v['sha256']) == 64 for v in result['assets'].values()))
        self.assertEqual(len({b['fbx_id'] for b in result['bones']}), result['bone_count'])

    def test_rejects_missing_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'missing or symlinked'):
                AUDIT.inspect(directory)

    def test_rejects_invalid_header(self):
        with self.assertRaisesRegex(ValueError, 'expected binary FBX'):
            AUDIT._nodes(b'broken FBX')


if __name__ == '__main__':
    unittest.main()
