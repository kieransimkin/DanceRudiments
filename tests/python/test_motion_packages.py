"""Optional-package regressions: lazy reads, integrity, identity and installation."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dancerudiments_authoring import (MotionPackage, MotionPackageBuilder, ScoreError,
    discover_motion_packages, export_motion_package, install_motion_package)
from dancerudiments_authoring._validation import canonical_json
from dancerudiments_authoring.motion import RigMotion
from dancerudiments_authoring.motion_packages import validate_manifest
from dancerudiments_authoring.recording import Recording, RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


def fixture(name='clip_one'):
    profile = RigProfile(rig_type_uri('package_test', kind='custom'), 'package_test', (
        RigChannel(1, 'root_x', 'root', 'location', 0, 'metre', -2, 2, 0),
        RigChannel(2, 'ik_parent', 'hand_ik', '["IK_parent"]', -1, 'index', 0, 4, 0,
                   value_type='integer', interpolation='step'),
    ))
    recording = Recording(name, profile.dimensions, ((-1, -1), (0, -0.5), (1, 1)),
                          RecordingClock(120, 'synthetic regression', start_pip=-1))
    return RigMotion(recording, profile)


class MotionPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'pack'
        self.motion = fixture()
        self.kwargs = dict(package_id='synthetic', version='1.0.0', title='Synthetic regression',
                           profile=self.motion.profile, license={'id': 'CC0-1.0'},
                           provenance={'synthetic': True})
        self.builder = MotionPackageBuilder(self.output, **self.kwargs)
        self.builder.add(self.motion, metadata={'timing_kind': 'music'})
        self.builder.add(fixture('clip_two'))
        self.manifest = self.builder.finalize()

    def test_import_has_no_optional_runtime_or_data_side_effects(self):
        result = subprocess.run([sys.executable, '-c',
            'import sys; import dancerudiments_authoring; '
            'assert "numpy" not in sys.modules; assert "bpy" not in sys.modules; '
            'assert "dancerudiments" not in sys.modules'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metadata_only_and_one_clip_lazy_cache(self):
        original = MotionPackage._asset
        reads = []
        def counted(package, descriptor):
            reads.append(descriptor['path'])
            return original(package, descriptor)
        with patch.object(MotionPackage, '_asset', counted):
            package = MotionPackage(self.output, expected_profile=self.motion.profile)
            self.assertEqual(len(package.catalogue()), 2)
            self.assertEqual(reads, [])
            first = package.load('clip_one')
            self.assertEqual(first, self.motion)
            self.assertEqual(reads, ['profile.json', 'clips/clip_one.json.gz'])
            self.assertIs(package.load('clip_one'), first)
            self.assertEqual(len(reads), 2)
            package.load('clip_two')
            self.assertEqual(package.cached_clip_ids, ('clip_two',))
            package.unload('clip_two')
            self.assertEqual(package.cached_clip_ids, ())
            package.close()
            with self.assertRaises(RuntimeError): package.load('clip_one')

    def test_wrong_target_profile_rejected_before_payload(self):
        modified = self.motion.profile.to_dict()
        modified['source']['rest'] = 'different skeleton'
        with self.assertRaisesRegex(ScoreError, 'retargeting'):
            MotionPackage(self.output, expected_profile=RigProfile.from_dict(modified))

    def test_asset_integrity_errors_are_retryable_and_not_cached(self):
        package = MotionPackage(self.output)
        asset = self.output / self.manifest['clips'][0]['path']
        good = asset.read_bytes()
        asset.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))
        with self.assertRaisesRegex(ScoreError, 'integrity'): package.load('clip_one')
        self.assertEqual(package.cached_clip_ids, ())
        asset.write_bytes(good)
        self.assertEqual(package.load('clip_one'), self.motion)

    def test_compressed_output_bound_and_content_identity(self):
        for change in ('size', 'identity', 'dimensions', 'discrete'):
            manifest = copy.deepcopy(self.manifest)
            desc = manifest['clips'][0]
            data = self.motion.recording.to_dict()
            if change == 'identity': data['name'] = 'other'
            if change == 'dimensions': data['dimensions'].reverse()
            if change == 'discrete': data['samples'][0][1] = -0.9
            payload = canonical_json(data).encode('ascii')
            stored = gzip.compress(payload)
            (self.output / desc['path']).write_bytes(stored)
            desc.update(sha256=hashlib.sha256(stored).hexdigest(), byte_length=len(stored),
                        decoded_byte_length=len(payload) - (1 if change == 'size' else 0))
            (self.output / 'manifest.json').write_text(canonical_json(manifest))
            with self.subTest(change=change), self.assertRaises(ScoreError):
                MotionPackage(self.output).load('clip_one')

    def test_manifest_contract_rejects_ambiguous_paths_and_versions(self):
        changes = (
            lambda d: d['profile'].update(path='manifest.json'),
            lambda d: d['profile'].update(path='README.md'),
            lambda d: d['clips'][0].update(path='../clip.json'),
            lambda d: d['clips'][0].update(path='https://example.com/clip.json'),
            lambda d: d['clips'][0].update(path='PROFILE.JSON'),
            lambda d: d['clips'][1].update(id=d['clips'][0]['id']),
            lambda d: d['clips'][0].update(sample_count=True),
            lambda d: d['clips'][0].update(start_pip=2147483647),
            lambda d: d['clips'][0]['metadata'].update(timing_kind='assumed'),
            lambda d: d.update(version='1.0.0-01'),
            lambda d: d.update(version='1.0.0-..'),
            lambda d: d.update(schema_version=True),
        )
        for mutate in changes:
            data = copy.deepcopy(self.manifest); mutate(data)
            with self.assertRaises(ScoreError): validate_manifest(data)
        data = dict(self.manifest, version='1.0.0-rc.1+pack.2')
        self.assertEqual(validate_manifest(data)['version'], data['version'])

    def test_deterministic_archives_and_atomic_install(self):
        first, second = self.root / 'first.zip', self.root / 'second.zip'
        (self.output / 'LICENSE.txt').write_text('Synthetic CC0 regression fixture.\n')
        export_motion_package(self.output, first)
        export_motion_package(self.output, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        with self.assertRaises(ScoreError):
            install_motion_package(first, self.root / 'bad', expected_sha256='0'*64)
        self.assertFalse((self.root / 'bad').exists())
        installed = install_motion_package(first, self.root / 'installed', expected_sha256=digest)
        self.assertEqual(MotionPackage(installed).load('clip_one'), self.motion)
        self.assertEqual(discover_motion_packages(self.root / 'installed')[0]['clip_count'], 2)
        with self.assertRaises(FileExistsError): install_motion_package(first, self.root / 'installed')

    def test_archive_paths_links_unknown_entries_and_hash_errors(self):
        for attack in ('../escape', 'symlink', 'undeclared', 'corrupt'):
            archive = self.root / f'{attack.replace("/", "_")}.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for path in self.output.rglob('*'):
                    if not path.is_file(): continue
                    relative = path.relative_to(self.output).as_posix()
                    payload = path.read_bytes()
                    if attack == 'corrupt' and relative.endswith('.gz'): payload = b'corrupt'
                    z.writestr(relative, payload)
                if attack == 'symlink':
                    info = zipfile.ZipInfo('README.md'); info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, '/tmp/escape')
                elif attack != 'corrupt': z.writestr(attack, b'bad')
            with self.subTest(attack=attack), self.assertRaises(ScoreError):
                install_motion_package(archive, self.root / 'rejected')
            self.assertFalse((self.root / 'rejected' / 'synthetic' / '1.0.0').exists())

    def test_package_assets_cannot_escape_using_symlinks(self):
        asset = self.output / self.manifest['clips'][0]['path']
        external = self.root / 'external.gz'
        asset.rename(external)
        try: asset.symlink_to(external)
        except OSError: self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(ScoreError, 'outside'): MotionPackage(self.output).load('clip_one')

    def test_resume_preserves_identity_and_rejects_duplicates(self):
        resumed = MotionPackageBuilder(self.output, **self.kwargs, resume=True)
        with self.assertRaises(ScoreError): resumed.add(self.motion)
        resumed.add(fixture('clip_three'), encoding='json')
        self.assertEqual(len(resumed.finalize()['clips']), 3)
        with self.assertRaises(ScoreError):
            MotionPackageBuilder(self.output, **dict(self.kwargs, title='Changed'), resume=True)

    def test_native_sample_through_optional_package(self):
        try: import dancerudiments
        except ImportError:
            import os
            if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE') == '1': raise
            self.skipTest('Native extension is required')
        motion = MotionPackage(self.output).load('clip_one')
        self.assertIsInstance(motion.to_native(), dancerudiments.SampledRecording)
        self.assertEqual(motion.player().by_channel(-1), {1: -2.0, 2: 0})


if __name__ == '__main__': unittest.main()
