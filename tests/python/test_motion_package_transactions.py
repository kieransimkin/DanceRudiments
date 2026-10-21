"""Failure-injection checks for resumable optional-package publication."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring import motion_packages as packages
from dancerudiments_authoring.motion import RigMotion
from dancerudiments_authoring.recording import Recording, RecordingClock
from dancerudiments_authoring.rigs import RigChannel, RigProfile, rig_type_uri


def fixture(name):
    profile = RigProfile(rig_type_uri('transaction_test', kind='custom'), 'transaction_test', (
        RigChannel(1, 'root_x', 'root', 'location', 0, 'metre', -2, 2, 0),
    ))
    recording = Recording(name, profile.dimensions, ((-1.,), (0.,), (1.,)),
                          RecordingClock(60, 'synthetic failure-injection fixture'))
    return RigMotion(recording, profile)


class MotionPackageTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='motion-package-transaction-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / 'package'
        self.first, self.second, self.third = (fixture(name) for name in ('complete_action', 'part_one', 'part_two'))
        self.kwargs = dict(package_id='transaction_test', version='1.0.0', title='Synthetic transaction',
                           profile=self.first.profile, license={'id': 'CC0-1.0'},
                           provenance={'synthetic': True})

    def builder(self, *, resume=False, **changes):
        return packages.MotionPackageBuilder(self.output, resume=resume, **dict(self.kwargs, **changes))

    def published_ids(self):
        if not (self.output / 'manifest.json').exists():
            return ()
        with packages.MotionPackage(self.output, cache_size=0) as package:
            return tuple(item['id'] for item in package.catalogue())

    def completed_builder(self):
        builder = self.builder()
        builder.add(self.first)
        builder.finalize()
        return builder

    def test_failure_during_initial_profile_write_can_resume(self):
        original = packages._write_bytes_document

        def fail_profile(path, *args, **kwargs):
            if Path(path).name == 'profile.json':
                raise OSError('injected profile write interruption')
            return original(path, *args, **kwargs)

        with patch.object(packages, '_write_bytes_document', side_effect=fail_profile):
            with self.assertRaises(OSError):
                self.builder()
        self.assertFalse((self.output / 'profile.json').exists())
        self.assertEqual(self.published_ids(), ())
        resumed = self.builder(resume=True)
        resumed.add(self.first)
        resumed.finalize()
        with packages.MotionPackage(self.output) as package:
            self.assertEqual(package.load(self.first.recording.name), self.first)

    def test_interrupted_output_cannot_be_claimed_by_different_identity(self):
        self.builder()
        original_files = {path.relative_to(self.output): path.read_bytes()
                          for path in self.output.rglob('*') if path.is_file()}
        with self.assertRaises(ScoreError):
            self.builder(resume=True, title='A different package')
        actual_files = {path.relative_to(self.output): path.read_bytes()
                        for path in self.output.rglob('*') if path.is_file()}
        self.assertEqual(actual_files, original_files)

    def test_identical_orphan_before_first_manifest_is_adopted(self):
        builder = self.builder()
        descriptor = builder.add(self.second)
        asset = self.output / descriptor['path']
        original = asset.read_bytes()
        self.assertEqual(self.published_ids(), ())
        resumed = self.builder(resume=True)
        resumed.add(self.second)
        resumed.finalize()
        self.assertEqual(asset.read_bytes(), original)
        self.assertEqual(self.published_ids(), (self.second.recording.name,))
        with packages.MotionPackage(self.output) as package:
            self.assertEqual(package.load(self.second.recording.name), self.second)

    def test_identical_orphan_after_a_checkpoint_is_adopted(self):
        builder = self.completed_builder()
        descriptor = builder.add(self.second)
        original = (self.output / descriptor['path']).read_bytes()
        self.assertEqual(self.published_ids(), (self.first.recording.name,))
        resumed = self.builder(resume=True)
        resumed.add(self.second)
        resumed.finalize()
        self.assertEqual((self.output / descriptor['path']).read_bytes(), original)
        self.assertEqual(self.published_ids(), (self.first.recording.name, self.second.recording.name))

    def test_changed_orphan_is_rejected_without_overwriting_it(self):
        builder = self.completed_builder()
        descriptor = builder.add(self.second)
        asset = self.output / descriptor['path']
        changed = asset.read_bytes() + b'changed orphan'
        asset.write_bytes(changed)
        manifest_before = (self.output / 'manifest.json').read_bytes()
        resumed = self.builder(resume=True)
        with self.assertRaises((ScoreError, FileExistsError)):
            resumed.add(self.second)
        self.assertEqual(asset.read_bytes(), changed)
        self.assertEqual((self.output / 'manifest.json').read_bytes(), manifest_before)

    def test_failed_first_action_never_publishes_partial_chunks(self):
        builder = self.builder()
        with self.assertRaises(OSError):
            with builder.atomic_batch():
                builder.add(self.second, metadata={'original_clip_id': 'one_action', 'chunk_index': 0, 'chunk_count': 2})
                raise OSError('injected second chunk failure')
        self.assertEqual(self.published_ids(), ())
        # An unrelated complete action may be published after the failed one;
        # the failed action's orphan bytes must remain unadvertised.
        with builder.atomic_batch():
            builder.add(self.first)
        self.assertEqual(self.published_ids(), (self.first.recording.name,))

    def test_failed_later_action_preserves_prior_manifest_and_can_retry(self):
        builder = self.completed_builder()
        manifest_before = (self.output / 'manifest.json').read_bytes()
        with self.assertRaises(OSError):
            with builder.atomic_batch():
                builder.add(self.second)
                self.assertEqual(self.published_ids(), (self.first.recording.name,))
                raise OSError('injected later chunk failure')
        self.assertEqual((self.output / 'manifest.json').read_bytes(), manifest_before)
        with builder.atomic_batch():
            builder.add(self.second)
            builder.add(self.third)
        self.assertEqual(self.published_ids(), tuple(m.recording.name for m in (self.first, self.second, self.third)))

    def test_keyboard_interrupt_does_not_publish_partial_action(self):
        builder = self.completed_builder()
        manifest_before = (self.output / 'manifest.json').read_bytes()
        with self.assertRaises(KeyboardInterrupt):
            with builder.atomic_batch():
                builder.add(self.second)
                raise KeyboardInterrupt()
        self.assertEqual((self.output / 'manifest.json').read_bytes(), manifest_before)
        with builder.atomic_batch():
            builder.add(self.second)
            builder.add(self.third)
        self.assertEqual(len(self.published_ids()), 3)

    def test_successful_batch_publishes_once_after_all_chunks(self):
        builder = self.completed_builder()
        writes = []
        original = packages._write_bytes_document

        def observe(path, *args, **kwargs):
            if Path(path).name == 'manifest.json':
                writes.append(path)
            return original(path, *args, **kwargs)

        with patch.object(packages, '_write_bytes_document', side_effect=observe):
            with builder.atomic_batch():
                builder.add(self.second)
                builder.add(self.third)
                self.assertEqual(self.published_ids(), (self.first.recording.name,))
                self.assertEqual(writes, [])
        self.assertEqual(len(writes), 1)
        self.assertEqual(len(self.published_ids()), 3)

    def test_manifest_write_failure_rolls_back_and_is_retryable(self):
        builder = self.completed_builder()
        manifest_before = (self.output / 'manifest.json').read_bytes()
        original = packages._write_bytes_document

        def fail_manifest(path, *args, **kwargs):
            if Path(path).name == 'manifest.json':
                raise OSError('injected commit failure')
            return original(path, *args, **kwargs)

        with patch.object(packages, '_write_bytes_document', side_effect=fail_manifest):
            with self.assertRaises(OSError):
                with builder.atomic_batch():
                    builder.add(self.second)
                    builder.add(self.third)
        self.assertEqual((self.output / 'manifest.json').read_bytes(), manifest_before)
        with builder.atomic_batch():
            builder.add(self.second)
            builder.add(self.third)
        self.assertEqual(len(self.published_ids()), 3)

    def test_clip_publication_followed_by_helper_error_is_retryable(self):
        builder = self.completed_builder()
        manifest_before = (self.output / 'manifest.json').read_bytes()
        original = packages._write_bytes_document

        def fail_after_write(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if Path(path).name == 'part_one.json.gz':
                raise OSError('injected cleanup error after successful clip publication')

        with patch.object(packages, '_write_bytes_document', side_effect=fail_after_write):
            with self.assertRaises(OSError):
                with builder.atomic_batch():
                    builder.add(self.second)
        asset = self.output / 'clips/part_one.json.gz'
        orphan_bytes = asset.read_bytes()
        self.assertEqual((self.output / 'manifest.json').read_bytes(), manifest_before)
        with builder.atomic_batch():
            builder.add(self.second)
            builder.add(self.third)
        self.assertEqual(asset.read_bytes(), orphan_bytes)
        self.assertEqual(len(self.published_ids()), 3)

    def test_manual_finalize_and_nested_batches_cannot_publish_early(self):
        builder = self.completed_builder()
        with builder.atomic_batch():
            builder.add(self.second)
            with self.assertRaises(ScoreError):
                builder.finalize()
            with self.assertRaises(ScoreError):
                with builder.atomic_batch():
                    pass
            self.assertEqual(self.published_ids(), (self.first.recording.name,))
            builder.add(self.third)
        self.assertEqual(len(self.published_ids()), 3)

    def test_installer_rejects_package_parent_symlink_outside_selected_root(self):
        self.completed_builder()
        archive = packages.export_motion_package(self.output, self.root / 'package.zip')
        selected, outside = self.root / 'installed', self.root / 'outside'
        selected.mkdir()
        outside.mkdir()
        link = selected / self.kwargs['package_id']
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlinks are unavailable')
        with self.assertRaises(ScoreError):
            packages.install_motion_package(archive, selected)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue(link.is_symlink())

    def test_collection_failure_keeps_next_complete_action_in_first_shard(self):
        try:
            import numpy  # noqa: F401 -- optional bulk-authoring dependency
        except ImportError:
            self.skipTest('NumPy is required for the focused BVH collection case')
        from dancerudiments_authoring import bvh_import
        repository = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('transaction_collection_importer',
                                                       repository / 'tools/import_motion_collection.py')
        importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(importer)
        cache = self.root / 'cache'
        cache.mkdir()
        header = ('HIERARCHY\nROOT Hips\n{\n OFFSET 0 0 0\n'
                  ' CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n'
                  ' End Site\n {\n  OFFSET 0 1 0\n }\n}\n'
                  'MOTION\nFrames: 5\nFrame Time: 0.015625\n')
        with zipfile.ZipFile(cache / 'source.zip', 'w') as zipped:
            for member, scale in (('A_interrupted.bvh', 1), ('B_complete.bvh', 2)):
                rows = ''.join(f'{frame * scale} 0 0 0 0 0\n' for frame in range(5))
                zipped.writestr(member, header + rows)
        source = dict(id='transaction_collection', title='Synthetic collection',
                      source_url='https://example.invalid/original-synthetic-fixture',
                      license=dict(id='CC0-1.0', url='https://creativecommons.org/publicdomain/zero/1.0/',
                                   attribution='Original synthetic regression fixture'),
                      archives=[dict(cache_path='source.zip', group='all',
                                     download_url='https://example.invalid/source.zip')])
        original = bvh_import.compile_bvh

        def interrupted(clip, **kwargs):
            for chunk in original(clip, **kwargs, max_chunk_values=len(clip.profile.channels) * 2):
                if clip.metadata['source_name'] == 'A_interrupted.bvh' and chunk.metadata['chunk_index'] == 1:
                    raise ScoreError('injected later chunk conversion failure')
                yield chunk

        with patch.object(bvh_import, 'compile_bvh', side_effect=interrupted), redirect_stdout(io.StringIO()):
            report = importer.build(source, cache, self.root / 'collection', max_clips=3)
        self.assertEqual(report['unique_actions'], 1)
        self.assertEqual(len(report['failures']), 1)
        self.assertEqual(len(report['packages']), 1)
        descriptor = report['packages'][0]
        self.assertTrue(descriptor['id'].endswith('_001'))
        with packages.MotionPackage(self.root / 'collection' / descriptor['manifest']) as package:
            clips = package.catalogue()
            self.assertEqual(len(clips), 3)
            self.assertEqual([c['metadata']['chunk_index'] for c in clips], [0, 1, 2])
            self.assertTrue(all(c['metadata']['source_member'] == 'B_complete.bvh' for c in clips))
            self.assertEqual([c['start_pip'] for c in clips], [0, 2, 4])
            self.assertEqual(sum(c['sample_count'] for c in clips), 5)


if __name__ == '__main__':
    unittest.main()
