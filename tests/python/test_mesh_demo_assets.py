"""Synthetic offline regression checks for the two optional mesh demo packages."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('build_mesh_demo_assets', ROOT / 'tools/build_mesh_demo_assets.py')
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)
import acquire_cmu_dance

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring.bvh_import import parse_bvh
from dancerudiments_authoring.motion_packages import MotionPackage

HAS_NUMPY = importlib.util.find_spec('numpy') is not None
HAS_NATIVE = importlib.util.find_spec('dancerudiments') is not None


def source_bytes(count, frame_time, height):
    rows = [f'{i/(count-1):.12f} 0 0 {i} 0 0 0 0 0' for i in range(count)]
    return (f'HIERARCHY\nROOT Hips\n{{\n OFFSET 0 0 0\n'
        ' CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation\n'
        f' JOINT Spine\n {{\n OFFSET 0 {height} 0\n CHANNELS 3 Zrotation Yrotation Xrotation\n'
        '  End Site\n  {\n   OFFSET 0 1 0\n  }\n }\n}\nMOTION\n'
        f'Frames: {count}\nFrame Time: {frame_time}\n' + '\n'.join(rows) + '\n').encode('ascii')


def fixture(root):
    commit = 'a' * 40
    licence = b'Synthetic test source terms; no third-party capture is used.\n'
    (root / 'source-terms.txt').write_bytes(licence)
    cache = root / 'cache'
    (cache / 'raw').mkdir(parents=True)
    document = dict(format='dancerudiments.mesh-demo-sources', schema_version=1,
        source_id='cmu_dance', mirror_commit=commit, conversion=deepcopy(demo.CONVERSION),
        license=dict(id='LicenseRef-CMU-Mocap', local_text='source-terms.txt',
            local_text_sha256=hashlib.sha256(licence).hexdigest(),
            attribution='Synthetic test only.', conversion_attribution='Synthetic fixture.'), scenes=[])
    payloads = {}
    for scene_id, motion_id, count, interval, height in (
            ('boxbot', '60_01', 61, '.0083333', 2), ('prism', '05_18', 31, '.01', 3)):
        payload = source_bytes(count, interval, height)
        path = cache / 'raw' / (motion_id + '.bvh')
        path.write_bytes(payload)
        clip = parse_bvh(payload, source_id='cmu_dance', **demo.CONVERSION)
        effective = Fraction(1, 60) if scene_id == 'boxbot' else Fraction(interval)
        repository_path = f'data/{motion_id.split("_")[0].zfill(3)}/{motion_id}.bvh'
        source = dict(id=motion_id, title='Synthetic dance ' + scene_id,
            cache_path='raw/' + motion_id + '.bvh', member='bvh/' + motion_id + '.bvh',
            repository_path=repository_path,
            download_url='https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/' + commit + '/' + repository_path,
            byte_length=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
            git_blob_sha1=hashlib.sha1(b'blob ' + str(len(payload)).encode('ascii') + b'\0' + payload).hexdigest(),
            source_url='https://example.org/synthetic/' + motion_id,
            frame_count=count, frame_time_seconds=str(Fraction(interval)),
            effective_frame_time_seconds=str(effective), effective_duration_seconds=float((count-1)*effective),
            calibration_frame_count=1, first_frame_kind='converter-added-calibration-t-pose',
            timing_kind='time-only', music_beat_metadata=None)
        if scene_id == 'boxbot':
            source['frame_time_override'] = dict(frame_time_seconds='1/60', evidence={'kind': 'synthetic-fixture'})
        document['scenes'].append(dict(id=scene_id, title='Synthetic ' + scene_id,
            description='Original synthetic fixture for tests.', characterKind=scene_id,
            packageId='mesh_demo_' + scene_id, version='1.0.0', source=source,
            expectedProfile=demo.profile_identity(clip.profile),
            sceneRigSha256=demo._sha(demo._bytes(demo.scene_rig(clip.profile, scene_id=scene_id, character_kind=scene_id)))))
        payloads[source['download_url']] = payload
    return document, cache, payloads


class MeshDemoRecipeTests(unittest.TestCase):
    def test_reviewed_recipe_has_only_two_distinct_small_sources(self):
        plan = demo.load_sources()
        self.assertEqual([s['id'] for s in plan['scenes']], ['boxbot', 'prism'])
        self.assertEqual([s['source']['id'] for s in plan['scenes']], ['60_01', '05_18'])
        self.assertEqual(sum(s['source']['byte_length'] for s in plan['scenes']), 3103529)
        self.assertEqual(plan['scenes'][0]['source']['frame_time_override']['frame_time_seconds'], '1/60')
        self.assertNotIn('frame_time_override', plan['scenes'][1]['source'])
        self.assertNotEqual(plan['scenes'][0]['expectedProfile']['fingerprint'],
                            plan['scenes'][1]['expectedProfile']['fingerprint'])

    def test_mutable_sources_unsafe_paths_and_unknown_rig_identity_are_rejected(self):
        original = demo.load_sources()
        mutations = [
            lambda p: p.update(mirror_commit='main'),
            lambda p: p['scenes'][0]['source'].update(download_url='https://example.org/unpinned.bvh'),
            lambda p: p['scenes'][0]['source'].update(repository_path='../source.bvh'),
            lambda p: p['scenes'][0]['source'].update(byte_length=5*1024*1024),
            lambda p: p['scenes'][0].update(sceneRigSha256=''),
            lambda p: p['scenes'][0]['source'].update(calibration_frame_count=0),
            lambda p: p['scenes'][0]['source'].update(timing_kind='music'),
            lambda p: p['scenes'][1].update(id='boxbot'),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                plan = deepcopy(original)
                mutate(plan)
                with self.assertRaises(ScoreError):
                    demo.validate_sources(plan)


@unittest.skipUnless(HAS_NUMPY and HAS_NATIVE, 'requires the optional offline NumPy extra and native recording extension')
class MeshDemoBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_parent = ROOT / '.cache/mesh-demo-tests'
        demo.preflight(cls.temporary_parent)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=self.temporary_parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plan, self.cache, self.payloads = fixture(self.root)
        self.output = self.root / 'assets'

    def build(self, **kwargs):
        return demo.build_assets(self.plan, self.output, cache_root=self.cache,
                                 license_root=self.root, **kwargs)

    def test_complete_native_packages_preserve_calibration_timing_and_bind_hierarchy(self):
        with mock.patch.object(acquire_cmu_dance.urllib.request, 'urlopen') as network:
            catalogue = self.build()
            network.assert_not_called()
        self.assertEqual([s['sampleCount'] for s in catalogue['scenes']], [65, 20])
        receipt = json.loads((self.output / 'verification.json').read_text())
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['verified_clips'], 2)
        self.assertEqual(receipt['complete_original_actions'], 2)
        self.assertFalse(any(Path(p['path']).is_absolute() for p in receipt['packages']))
        for scene, configured in zip(catalogue['scenes'], self.plan['scenes']):
            directory = self.output / 'motions' / scene['id']
            self.assertEqual(scene['startPip'], 0)
            self.assertEqual(scene['endPip'], scene['sampleCount']-1)
            self.assertEqual(scene['calibrationFrameCount'], 1)
            self.assertEqual(scene['trimmedSourceFrames'], 0)
            self.assertFalse(scene['musicTimingVerified'])
            self.assertEqual(scene['expectedProfile'], configured['expectedProfile'])
            self.assertEqual(demo._sha((directory/'scene-rig.json').read_bytes()), configured['sceneRigSha256'])
            self.assertEqual(demo._sha((directory/'manifest.json').read_bytes()), scene['manifestSha256'])
            self.assertEqual(demo._sha((directory/'browser-reference.json').read_bytes()), scene['browserReferenceSha256'])
            self.assertEqual((directory/'LICENSE.txt').read_bytes(), (self.root/'source-terms.txt').read_bytes())
            self.assertFalse((directory/'.motion-package-build.json').exists())
            rig = json.loads((directory/'scene-rig.json').read_text())
            self.assertEqual([j['parentIndex'] for j in rig['joints']], [-1, 0])
            self.assertEqual(rig['joints'][0]['positionChannelIndices'], [0, 1, 2])
            self.assertEqual(rig['joints'][0]['rotationChannelIndices'], [3, 4, 5, 6])
            self.assertIsNone(rig['joints'][1]['positionChannelIndices'])
            self.assertEqual(rig['joints'][1]['offset'], [0., 0., 2. if scene['id']=='boxbot' else 3.])
            self.assertEqual(rig['joints'][1]['endSites'], [[0., 0., 1.]])
            reference = json.loads((directory/'browser-reference.json').read_text())
            self.assertEqual(reference['jointNames'], ['Hips', 'Spine'])
            self.assertEqual(reference['matrixLayout'], 'row-major')
            self.assertEqual(reference['manifestSha256'], scene['manifestSha256'])
            self.assertEqual([s['pip'] for s in reference['samples']],
                             sorted({0, scene['sampleCount']//2, scene['endPip']}))
            with MotionPackage(directory, cache_size=0) as package:
                motion = package.load(scene['clipIds'][0])
                for sample in reference['samples']:
                    self.assertEqual(sample['physicalValues'], list(motion.player().sample(sample['pip'])))
                metadata = motion.recording.provenance
                self.assertEqual(metadata['source_sha256'], configured['source']['sha256'])
                self.assertEqual(metadata['calibration_frame_count'], 1)
                self.assertEqual(metadata['trimmed_source_frames'], 0)
                self.assertIsNone(metadata['musical_bpm'])
                self.assertAlmostEqual(motion.player().sample(0)[0], 0., places=7)
                if scene['id'] == 'boxbot':
                    self.assertEqual(metadata['frame_time_override']['original_header']['frame_time_fraction'], '83333/10000000')
                    self.assertEqual(metadata['source_frame_time_fraction'], '1/60')
                    self.assertAlmostEqual(motion.player().sample(64)[0], 1., places=7)
                    # Independent analytic endpoint: source Z rotation 60deg
                    # maps to -Y in the carrier. A two-unit +Z rest offset must
                    # therefore end at (1-sqrt(3), 0, 1) after root translation.
                    child = reference['samples'][-1]['jointWorldMatrices'][1]
                    for actual, expected in zip((child[3], child[7], child[11]), (1-math.sqrt(3), 0., 1.)):
                        self.assertAlmostEqual(actual, expected, places=7)
                    self.assertEqual(child[12:], [0., 0., 0., 1.])
                else:
                    self.assertNotIn('frame_time_override', metadata)
            original = configured['source']
            self.assertEqual((self.cache/original['cache_path']).read_bytes(), self.payloads[original['download_url']])
        self.assertFalse(list(self.output.rglob('*.bvh')))
        before = (self.output/'catalogue.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual((self.output/'catalogue.json').read_bytes(), before)

    def test_download_is_explicit_and_only_requests_two_selected_files(self):
        for path in (self.cache/'raw').glob('*.bvh'):
            path.unlink()
        with mock.patch.object(acquire_cmu_dance.urllib.request, 'urlopen') as network:
            with self.assertRaises(FileNotFoundError):
                self.build()
            network.assert_not_called()
        self.assertFalse(self.output.exists())

        def response(request, **kwargs):
            stream = io.BytesIO(self.payloads[request.full_url])
            stream.status = 200
            return stream

        with mock.patch.object(acquire_cmu_dance.urllib.request, 'urlopen', side_effect=response) as network:
            self.build(download=True)
        self.assertEqual(network.call_count, 2)
        self.assertEqual({call.args[0].full_url for call in network.call_args_list}, set(self.payloads))
        self.assertFalse(list(self.cache.rglob('*.zip')))

    def test_tampered_source_or_scene_identity_cannot_publish(self):
        source = self.plan['scenes'][0]['source']
        path = self.cache/source['cache_path']
        original = path.read_bytes()
        path.write_bytes(original.replace(b'HIERARCHY', b'hIERARCHY', 1))
        with self.assertRaisesRegex(ValueError, 'source hash'):
            self.build()
        self.assertFalse(self.output.exists())
        path.write_bytes(original)
        self.plan['scenes'][0]['expectedProfile']['fingerprint'] = '0'*64
        with self.assertRaisesRegex(ScoreError, 'independently pinned scene identity'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_failed_rig_or_native_verification_leaves_no_published_assets(self):
        original = self.plan['scenes'][0]['sceneRigSha256']
        self.plan['scenes'][0]['sceneRigSha256'] = '0'*64
        with self.assertRaisesRegex(ScoreError, 'independently pinned rig hash'):
            self.build()
        self.plan['scenes'][0]['sceneRigSha256'] = original
        with mock.patch.object(demo, 'verify_packages', return_value={'passed':False, 'failures':[{'error':'synthetic failure'}]}):
            with self.assertRaisesRegex(ScoreError, 'Native demo verification failed'):
                self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.mesh-demo-build-*')))


if __name__ == '__main__':
    unittest.main()
