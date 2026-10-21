"""Synthetic checks for pinned CMU source acquisition; no external assets/network."""
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
SPEC = importlib.util.spec_from_file_location('acquire_cmu_dance', ROOT / 'tools/acquire_cmu_dance.py')
acquisition = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquisition)

SYNTHETIC = (b'HIERARCHY\nROOT Hips\n{\n OFFSET 0 0 0\n'
             b' CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation\n'
             b' End Site\n {\n OFFSET 0 1 0\n }\n}\nMOTION\nFrames: 2\n'
             b'Frame Time: .0083333\n0 0 0 0 0 0\n1 0 0 0 0 0\n')


def fixture(root):
    commit = 'a' * 40
    source = root / 'raw/05_02.bvh'
    source.parent.mkdir()
    source.write_bytes(SYNTHETIC)
    licence = root / 'synthetic-terms.txt'
    licence.write_bytes(b'Synthetic test terms only; no captured motion.\n')
    item = dict(id='05_02', cache_path='raw/05_02.bvh', member='bvh/05_02.bvh',
                download_url='https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/' + commit + '/data/005/05_02.bvh',
                byte_length=len(SYNTHETIC), sha256=hashlib.sha256(SYNTHETIC).hexdigest(),
                git_blob_sha1=hashlib.sha1(b'blob ' + str(len(SYNTHETIC)).encode() + b'\0' + SYNTHETIC).hexdigest(),
                calibration_frame_count=1,
                frame_time_override={'frame_time_seconds': '1/60', 'evidence': {'kind': 'synthetic-fixture'}})
    document = dict(format='dancerudiments.cmu-dance-source-files', schema_version=1,
                    source_id='cmu_dance', mirror_commit=commit, files=[item], support_files=[],
                    license={'id': 'LicenseRef-CMU-Mocap', 'local_text_sha256': acquisition._digest(licence)},
                    archive={'name': 'cmu-dance-original-bvh.zip', 'sha256': '0' * 64})
    expected = root / 'expected.zip'
    with mock.patch.object(acquisition, 'LICENSE_PATH', licence):
        acquisition._write_archive(document, root, expected)
    document['archive']['sha256'] = acquisition._digest(expected)
    expected.unlink()
    return document, licence


class CMUAcquisitionTests(unittest.TestCase):
    def test_rebuild_keeps_original_header_calibration_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document, licence = fixture(root)
            manifest = root / 'source.json'
            manifest.write_bytes(acquisition._json_bytes(document))
            document = acquisition.load_manifest(manifest)
            with mock.patch.object(acquisition, 'LICENSE_PATH', licence), mock.patch.object(acquisition.urllib.request, 'urlopen') as network:
                first = acquisition.acquire(document, root)
                network.assert_not_called()
                archive = Path(first['path'])
                original_zip = archive.read_bytes()
                with zipfile.ZipFile(archive) as data:
                    self.assertEqual(data.read('bvh/05_02.bvh'), SYNTHETIC)
                    record = json.loads(data.read('source-record.json'))
                    self.assertEqual(record['files'][0]['calibration_frame_count'], 1)
                    self.assertEqual(record['files'][0]['frame_time_override']['frame_time_seconds'], '1/60')
                archive.unlink()
                second = acquisition.acquire(document, root)
                self.assertEqual(Path(second['path']).read_bytes(), original_zip)

    def test_cached_data_requires_both_git_blob_and_sha256_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document, licence = fixture(root)
            document['files'][0]['git_blob_sha1'] = 'b' * 40
            with mock.patch.object(acquisition, 'LICENSE_PATH', licence):
                with self.assertRaisesRegex(ValueError, 'source hash'):
                    acquisition.acquire(document, root)
            self.assertEqual((root / 'raw/05_02.bvh').read_bytes(), SYNTHETIC)
            self.assertFalse((root / document['archive']['name']).exists())

    def test_download_requires_opt_in_and_failed_download_can_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document, licence = fixture(root)
            source = root / 'raw/05_02.bvh'; source.unlink()
            with mock.patch.object(acquisition.urllib.request, 'urlopen') as network:
                with self.assertRaises(FileNotFoundError):
                    acquisition.acquire(document, root)
                network.assert_not_called()

            def response(data):
                value = io.BytesIO(data); value.status = 200
                return value

            with mock.patch.object(acquisition.urllib.request, 'urlopen', return_value=response(b'bad response')):
                with self.assertRaises(ValueError):
                    acquisition.acquire(document, root, download=True)
            self.assertFalse(source.exists())
            self.assertEqual(list((root / 'raw').glob('.cmu-*')), [])
            with mock.patch.object(acquisition.urllib.request, 'urlopen', return_value=response(SYNTHETIC)), mock.patch.object(acquisition, 'LICENSE_PATH', licence):
                report = acquisition.acquire(document, root, download=True)
            self.assertTrue(Path(report['path']).is_file())

    def test_manifest_rejects_mutable_urls_paths_and_oversized_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline, _ = fixture(root)
            mutations = [
                lambda x: x.update(mirror_commit='master'),
                lambda x: x['files'][0].update(cache_path='../outside.bvh'),
                lambda x: x['files'][0].update(member='LICENSE.txt'),
                lambda x: x['files'][0].update(download_url='https://example.com/file.bvh'),
                lambda x: x['files'][0].update(byte_length=9 * 1024 * 1024),
                lambda x: x['files'].append(deepcopy(x['files'][0])),
            ]
            for mutate in mutations:
                document = deepcopy(baseline); mutate(document)
                manifest = root / 'invalid.json'; manifest.write_bytes(acquisition._json_bytes(document))
                with self.assertRaises(ValueError):
                    acquisition.load_manifest(manifest)


if __name__ == '__main__':
    unittest.main()
