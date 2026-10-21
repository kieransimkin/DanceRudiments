"""Synthetic acquisition checks; no network or third-party motion fixtures."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('acquire_space_xr', ROOT / 'tools/acquire_space_xr.py')
acquisition = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquisition)

SYNTHETIC = b'HIERARCHY\nROOT synthetic\nMOTION\nFrames: 1\nFrame Time: 0.01\n0\n'


def fixture(root):
    item = dict(name='synthetic.bvh', member='bvh/synthetic.bvh',
                download_url='https://visgraflab.impa.br/dance/wp-content/uploads/2023/09/synthetic.bvh',
                original_url='http://visgraflab.impa.br/dance/wp-content/uploads/2023/09/synthetic.bvh',
                sha256=hashlib.sha256(SYNTHETIC).hexdigest(), byte_length=len(SYNTHETIC),
                title='Synthetic test only', performer='Synthetic fixture')
    group = dict(id='space_xr_yup', archive_name='space-xr-yup-test.zip',
                 sha256='0' * 64, conversion={}, files=[item])
    document = dict(format='dancerudiments.space-xr-source-files', schema_version=1,
                    title='Synthetic acquisition test', creator='Synthetic fixture',
                    source_url='https://visgraflab.impa.br/dance/?p=1',
                    license={'spdx': 'CC-BY-SA-4.0'}, physical_unit='synthetic',
                    source_page_sha256='1' * 64, notes=['Synthetic; no captured asset.'],
                    archives=[group])
    (root / item['name']).write_bytes(SYNTHETIC)
    archive = root / 'expected.zip'
    acquisition._write_archive(document, group, root, archive)
    group['sha256'] = acquisition._digest(archive)
    archive.unlink()
    return document


class SpaceXRAcquisitionTests(unittest.TestCase):
    def test_cached_build_is_deterministic_and_keeps_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = fixture(root)
            manifest = root / 'source.json'
            manifest.write_bytes(acquisition._json_bytes(document))
            document = acquisition.load_manifest(manifest)
            with mock.patch.object(acquisition.urllib.request, 'urlopen') as network:
                first = acquisition.acquire(document, root)
                network.assert_not_called()
            archive = Path(first[0]['path'])
            expected = archive.read_bytes()
            with zipfile.ZipFile(archive) as data:
                self.assertEqual(data.read('bvh/synthetic.bvh'), SYNTHETIC)
                record = json.loads(data.read('source-record.json'))
                self.assertEqual(record['files'][0]['original_url'], document['archives'][0]['files'][0]['original_url'])
                self.assertEqual(record['timing_kind'], 'time-only')
                self.assertIsNone(record['music_beat_metadata'])
            archive.unlink()
            second = acquisition.acquire(document, root)
            self.assertEqual(Path(second[0]['path']).read_bytes(), expected)
            self.assertEqual(first, second)

    def test_download_requires_opt_in_and_corrupt_download_can_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = fixture(root)
            source = root / 'synthetic.bvh'
            source.unlink()
            with mock.patch.object(acquisition.urllib.request, 'urlopen') as network:
                with self.assertRaises(FileNotFoundError):
                    acquisition.acquire(document, root)
                network.assert_not_called()

            def response(data):
                value = io.BytesIO(data)
                value.status = 200
                value.headers = {'Content-Length': str(len(data))}
                return value

            corrupted = SYNTHETIC[:-2] + b'1\n'
            with mock.patch.object(acquisition.urllib.request, 'urlopen', return_value=response(corrupted)):
                with self.assertRaisesRegex(ValueError, 'hash/size'):
                    acquisition.acquire(document, root, download=True)
            self.assertFalse(source.exists())
            self.assertEqual(list(root.glob('.space-xr-*')), [])
            with mock.patch.object(acquisition.urllib.request, 'urlopen', return_value=response(SYNTHETIC)):
                report = acquisition.acquire(document, root, download=True)
            self.assertEqual(source.read_bytes(), SYNTHETIC)
            self.assertTrue(Path(report[0]['path']).is_file())

    def test_integrity_failure_does_not_overwrite_cache_or_publish_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = fixture(root)
            group = document['archives'][0]
            group['sha256'] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'deterministic archive hash'):
                acquisition.acquire(document, root)
            self.assertFalse((root / group['archive_name']).exists())
            source = root / 'synthetic.bvh'
            source.write_bytes(b'X' * len(SYNTHETIC))
            with mock.patch.object(acquisition.urllib.request, 'urlopen') as network:
                with self.assertRaisesRegex(ValueError, 'cached bytes'):
                    acquisition.acquire(document, root, download=True)
                network.assert_not_called()
            self.assertEqual(source.read_bytes(), b'X' * len(SYNTHETIC))

    def test_manifest_rejects_unsafe_members_urls_duplicates_and_resource_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = fixture(root)
            mutations = [
                lambda x: x['archives'][0]['files'][0].update(member='../outside.bvh'),
                lambda x: x['archives'][0]['files'][0].update(download_url='http://visgraflab.impa.br/dance/wp-content/uploads/2023/09/synthetic.bvh'),
                lambda x: x['archives'][0]['files'][0].update(byte_length=acquisition.MAX_FILE_BYTES + 1),
                lambda x: x['archives'][0]['files'].append(deepcopy(x['archives'][0]['files'][0])),
                lambda x: x['archives'][0].update(archive_name='../outside.zip'),
            ]
            for mutate in mutations:
                document = deepcopy(baseline)
                mutate(document)
                path = root / 'invalid.json'
                path.write_bytes(acquisition._json_bytes(document))
                with self.assertRaises(ValueError):
                    acquisition.load_manifest(path)


if __name__ == '__main__':
    unittest.main()
