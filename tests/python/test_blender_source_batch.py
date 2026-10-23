"""Blender extracted Action index → confidence-shortlisted complete and loop clips."""
from __future__ import annotations
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from dancerudiments_authoring.motion_import import write_capture
from test_source_loop_analysis import fixture
from test_full_motion_confidence import fake_rhythmic_stemlab

TOOLS=Path(__file__).resolve().parents[2]/'tools'
sys.path.insert(0,str(TOOLS))
spec=importlib.util.spec_from_file_location('blender_capture_batch',TOOLS/'analyze_blender_capture_batch.py')
batch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def inputs(directory, *, mismatched=False):
    root=Path(directory)/'extracted';root.mkdir()
    original='d'*64
    capture=fixture()
    provenance=dict(capture.provenance, source_file={'filename':'original.glb','sha256':original})
    capture=replace(capture,provenance_json=json.dumps(provenance))
    write_capture(root/'action.capture.json',capture)
    index={'format':'dancerudiments.blender-import','schema_version':1,
           'source':{'filename':'original.glb','sha256':original},
           'captures':[{'capture':'action.capture.json','binding_id':'original_action',
                        'profile_sha256':('0'*64 if mismatched else capture.profile.fingerprint)}]}
    (root/'index.json').write_text(json.dumps(index))
    return root/'index.json'


class BlenderBatchTests(unittest.TestCase):
    def test_full_action_and_independent_loop_are_preserved_with_source_sha(self):
        with tempfile.TemporaryDirectory() as dir, mock.patch.dict(sys.modules,fake_rhythmic_stemlab()):
            index=inputs(dir);out=Path(dir)/'results'
            result=batch.analyse_batch(index,out)
            self.assertEqual(result['full_motion_count'],1)
            self.assertEqual(result['loopable_clip_count'],1)
            self.assertEqual(result['failed_action_count'],0)
            self.assertEqual(result['source_file_sha256'],'d'*64)
            self.assertEqual(result['full_motion_shortlist'][0]['original_source_sha256'],'d'*64)
            self.assertGreaterEqual(result['full_motion_shortlist'][0]['confidence_percent'],70)
            self.assertEqual(len(list(out.glob('*/job.json'))),1)
            self.assertTrue(index.is_file())

    def test_index_profile_disagreement_rejects_action(self):
        with tempfile.TemporaryDirectory() as dir, mock.patch.dict(sys.modules,fake_rhythmic_stemlab()):
            index=inputs(dir,mismatched=True)
            result=batch.analyse_batch(index,Path(dir)/'results')
            self.assertEqual(result['full_motion_count'],0)
            self.assertEqual(result['failed_action_count'],1)
            self.assertIn('rig profile', result['failures'][0]['error'])

    def test_path_traversal_is_rejected_without_accessing_adjacent_files(self):
        with tempfile.TemporaryDirectory() as dir, mock.patch.dict(sys.modules,fake_rhythmic_stemlab()):
            index=inputs(dir);d=json.loads(index.read_text())
            d['captures'][0]['capture']='../secret.capture.json'
            index.write_text(json.dumps(d))
            result=batch.analyse_batch(index,Path(dir)/'results')
            self.assertEqual(result['failed_action_count'],1)
            self.assertIn('direct .capture.json',result['failures'][0]['error'])


if __name__=='__main__':
    unittest.main()
