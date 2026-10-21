"""End-to-end archive import, source counts, resumability and package boundaries."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from dancerudiments_authoring import MotionPackage
from test_bvh_import import fixture, np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('motion_collection_tool', ROOT / 'tools/import_motion_collection.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@unittest.skipIf(np is None, 'optional NumPy import dependency unavailable')
class MotionCollectionTests(unittest.TestCase):
    def test_complete_archive_import_counts_sources_and_preserves_notices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = fixture(((1, 2, 3, 0, 0, 0), (2, 3, 4, 20, 30, 40)), dt='0.1')
            second = fixture(((1, 2, 3, 0, 0, 0), (4, 3, 4, 20, 30, 40)), dt='0.1')
            archive = root / 'source.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('A/first.bvh', first)
                z.writestr('B/second.bvh', second)
                z.writestr('C/duplicate.bvh', first)
                z.writestr('D/broken.bvh', 'not a BVH')
            source = {'id': 'synthetic', 'title': 'Synthetic fixtures', 'source_url': 'https://example.invalid/synthetic',
                'license': {'id': 'CC0-1.0', 'url': 'https://creativecommons.org/publicdomain/zero/1.0/',
                            'attribution': 'Synthetic regression fixture'},
                'conversion': {'root_offset_policy': 'motion', 'translation_convention': 'blender-absolute'},
                'archives': [{'cache_path': 'source.zip', 'download_url': 'https://example.invalid/source.zip',
                              'sha256': tool.file_hash(archive), 'size_bytes': archive.stat().st_size, 'group': 'fixtures'}]}
            with contextlib.redirect_stdout(io.StringIO()):
                report = tool.build(source, root, root / 'packages')
            self.assertEqual(report['unique_actions'], 2)
            self.assertEqual(report['recording_chunks'], 2)
            self.assertEqual(len(report['duplicate_files']), 1)
            self.assertEqual(len(report['failures']), 1)
            self.assertEqual(len(report['packages']), 1)
            path = root / 'packages' / report['packages'][0]['id'] / '1.0.0'
            package = MotionPackage(path)
            self.assertEqual(len(package.catalogue()), 2)
            for clip in package.catalogue():
                self.assertEqual(clip['metadata']['timing_kind'], 'time-only')
                self.assertEqual(len(package.load(clip['id']).recording.samples), 7)
            self.assertIn('Synthetic regression fixture', (path / 'THIRD_PARTY_NOTICES.md').read_text())
            before = (path / 'manifest.json').read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                resumed = tool.build(source, root, root / 'packages', resume=True)
            self.assertEqual(resumed['unique_actions'], 2)
            self.assertEqual(before, (path / 'manifest.json').read_bytes())

if __name__ == '__main__': unittest.main()
