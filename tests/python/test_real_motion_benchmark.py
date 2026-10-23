"""No-network provenance-only checks for pinned real motion benchmark reports."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('real_motion_evaluation',
                                            HERE/'tools/evaluate_real_rig_motions.py')
benchmark=importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def fixture():
    recipe={'mirror_commit':'1'*40,'license':{'id':'LicenseRef-CMU-Mocap'}}
    scene={'id':'boxbot','source':{'id':'60_01','title':'Salsa',
           'sha256':'a'*64,'source_url':'https://example.invalid/synthetic.bvh'}}
    profile=SimpleNamespace(fingerprint='b'*64,type_uri='syn://type/test/source/human')
    clip=SimpleNamespace(source_sha256='a'*64,profile=profile,
                         frame_count=400,source_fps=60,duration_seconds=6.65)
    report={'source_original_sha256':'a'*64,'profile_sha256':'b'*64,
            'full_motion_count':1,'full_motion_fit':{
                'confidence':.81,'confidence_percent':81.,'threshold':.70,
                'method':'dancerudiments.full-motion-grid-fit.v1',
                'confidence_interpretation':'uncalibrated_kinematic_fit_not_probability',
                'selected_bpm':120.,'reasons':[],
                'tempo_hypotheses':[{'bpm':120.,'fit_score':.83,
                                     'metrical_relation_to_top':'primary','notes':[]}]},
            'loopable_clip_count':2,'unconverted_candidate_count':6}
    return recipe,scene,clip,report


class RealMotionSummaryTests(unittest.TestCase):
    def test_report_contains_only_identifiers_and_confidence_no_original_samples(self):
        row=benchmark.summarize_action(*fixture())
        self.assertEqual(row['source_sha256'],'a'*64)
        self.assertEqual(row['profile_sha256'],'b'*64)
        self.assertEqual(row['source_license_id'],'LicenseRef-CMU-Mocap')
        self.assertEqual(row['bpm_estimated'],120)
        self.assertEqual(row['number_of_source_loop_candidates'],8)
        self.assertTrue(row['full_action_shortlisted'])
        self.assertFalse(row['beat_alignment_confirmed'])
        self.assertFalse(row['loop_seam_approved'])
        self.assertFalse(set(row)&{'frames','samples','source_frames_array',
                                   'motion','clip','recording','audio'})

    def test_modified_source_sha_or_profile_is_rejected(self):
        for field in ('source_original_sha256','profile_sha256'):
            values=list(fixture())
            values[3][field]='c'*64
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'identity'):
                benchmark.summarize_action(*values)

    def test_unjustified_auto_conversion_not_reported(self):
        args=list(fixture())
        args[3]['full_motion_fit']['confidence']=.15
        with self.assertRaisesRegex(ValueError,'confidence gating'):
            benchmark.summarize_action(*args)


if __name__=='__main__':unittest.main()
