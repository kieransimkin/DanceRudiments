"""Music+motion CI gallery tests: synthetic fixture only, no downloads/media distribution."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

TOOL = Path(__file__).resolve().parents[2]/'tools'/'build_song_loop_preview.py'
spec=importlib.util.spec_from_file_location('song_loop_preview',TOOL)
preview=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=preview
spec.loader.exec_module(preview)


class SongLoopPreviewTests(unittest.TestCase):
    def test_grid_is_strict_about_music_phase(self):
        good=[i*.5 for i in range(20)]
        self.assertEqual(len(preview._validate_grid(good, good[::4], 10)[0]),20)
        for broken in ([-.1]+good[1:],good[:5]+[good[4]]+good[6:]):
            with self.assertRaises(ValueError):
                preview._validate_grid(broken, good[::4], 10)
        with self.assertRaisesRegex(ValueError,'observed beat'):
            preview._validate_grid(good, [0.15,2.15],10)
        with self.assertRaisesRegex(ValueError,'8 beats'):
            preview._validate_grid(good[:3],[],10)

    def test_estimated_music_matches_do_not_claim_approval(self):
        song={'grid':{'bpm':120.,'beats':[i*.5 for i in range(100)]}}
        motions=[{'id':'four','beats':4,'estimated_bpm':120,'score':.9},
                 {'id':'three','beats':3,'estimated_bpm':120,'score':.9},
                 {'id':'sixteen','beats':16,'estimated_bpm':280,'score':.9}]
        audio={'sample_rate':100,'loops':[],
               'exploratory_candidates':[{'id':'whole-01-x01','bars':2,'grid_start_sample':0,
                                          'start_seconds':0,'end_seconds':4,'status':'requires_listening_or_edit',
                                          'failed_gates':['full_vocal_evidence_missing'],
                                          'exploratory_ranking_cost':.12}]}
        ranks=preview._rank_matches(song,motions,audio)
        self.assertEqual([x['motion_id'] for x in ranks],['four'])
        self.assertEqual(ranks[0]['motion_repeats'],2)
        self.assertEqual(ranks[0]['audio_failed_gates'],['full_vocal_evidence_missing'])
        self.assertFalse(ranks[0]['beat_alignment_confirmed'])
        self.assertFalse(ranks[0]['loop_seam_approved'])

    def test_complete_action_is_never_implicitly_repeated(self):
        song={'grid':{'bpm':120.,'beats':[i*.5 for i in range(100)]}}
        motions=[dict(id='whole',beats=16.0,estimated_bpm=120.,score=.84,
                      motion_kind='full_length',full_motion_confidence=.84),
                 dict(id='loop',beats=4.0,estimated_bpm=120.,score=.8,
                      motion_kind='loopable')]
        audio={'sample_rate':100,'loops':[], 'exploratory_candidates':[
            dict(id='whole-01-x01',bars=4,grid_start_sample=0,
                 start_seconds=0,end_seconds=8,status='requires_listening_or_edit',
                 failed_gates=[],exploratory_ranking_cost=.12),
            dict(id='whole-01-x02',bars=2,grid_start_sample=0,
                 start_seconds=0,end_seconds=4,status='requires_listening_or_edit',
                 failed_gates=[],exploratory_ranking_cost=.12)]}
        pairs=preview._rank_matches(song,motions,audio)
        whole=[x for x in pairs if x['motion_id']=='whole']
        self.assertEqual(len(whole),1)
        self.assertEqual(whole[0]['motion_repeats'],1)
        self.assertEqual(whole[0]['motion_kind'],'full_length')
        self.assertEqual(whole[0]['full_motion_confidence'],.84)
        loops=[x for x in pairs if x['motion_id']=='loop']
        self.assertEqual({x['motion_repeats'] for x in loops},{2,4})
        self.assertTrue(all(not x['beat_alignment_confirmed'] for x in pairs))

    @unittest.skipUnless(importlib.util.find_spec('numpy'),'NumPy needed for offline FK sample')
    def test_fk_source_preview_preserves_64_pip_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'sample.motion.json'
            def bone(name,parent,z):
                return {'name':name,'parent':parent,'rest_matrix':
                        [1,0,0,0,0,1,0,0,0,0,1,z,0,0,0,1]}
            data={'format':'dancerudiments.rig-motion','profile_sha256':'a'*64,
                  'profile':{'channels':[
                     {'name':f'root_{a}','bone':'root','data_path':'location','array_index':i,
                      'minimum':-1,'maximum':1} for i,a in enumerate('xyz')],
                     'source':{'skeleton':[bone('root',None,0),bone('child','root',1)],
                               'omitted_neutral_groups':[]}},
                  'recording':{'name':'source_four','samples':[[(i/63)*2-1, 0, 0] for i in range(64)]}}
            p.write_text(json.dumps(data))
            output=preview._motion_to_frames(p, max_frames=8)
            self.assertEqual(output['frame_count'],8)
            self.assertEqual(output['beats'],1)
            self.assertEqual(output['links'],[[0,1]])
            self.assertEqual(output['skeleton_kind'],'source_portable_fk')
            self.assertAlmostEqual(output['xyz'][-1][0][0],1)
            self.assertAlmostEqual(output['xyz'][-1][1][2],1)

    @unittest.skipUnless(importlib.util.find_spec('soundfile') and importlib.util.find_spec('numpy'),
                         'Small synthetic audio requires soundfile and NumPy')
    def test_complete_gallery_is_audio_free_and_handles_song_failures(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'stemlab';file=root/'examples'/'test'/'master.wav'
            file.parent.mkdir(parents=True)
            samples=np.zeros(44100*8,dtype='float32')
            for i in range(16):
                pos=round(i*.5*44100)
                samples[pos:pos+600]+=np.hanning(600)*.7
            sf.write(file,samples,44100)
            reference=file.parent/'reference.json'
            reference.write_text(json.dumps({'title':'Synthetic','artist':'Test',
                                  'bpm':120,'example_audio':{'sha256':preview._hash(file)}}))
            src=root/'src/stemlab/analysis';src.mkdir(parents=True)
            (src/'__init__.py').write_text('')
            (src.parent/'__init__.py').write_text('')
            (src/'loops.py').write_text('''import json\nfrom pathlib import Path\nclass LoopConfig:\n    def __init__(self, **kwargs): self.__dict__.update(kwargs)\ndef analyze_loops(audio, output_dir, **kwargs):\n    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)\n    from hashlib import sha256\n    digest=sha256(Path(audio).read_bytes()).hexdigest()\n    data={'source_sha256':digest,'sample_rate':44100,'loop_count':0,'loops':[],\n        'exploratory_count':1,'exploratory_candidates':[{'id':'whole-01-x01','bars':1,\n        'grid_start_sample':0,'start_seconds':0,'end_seconds':2,'status':'requires_listening_or_edit',\n        'failed_gates':['full_vocal_evidence_missing'],'exploratory_ranking_cost':.22}]}\n    (output_dir/'loops.json').write_text(json.dumps(data));return data\n''')
            (src.parent/'types.py').write_text('''class BeatResult:\n    def __init__(self, **kwargs): self.__dict__.update(kwargs)\n''')
            job=Path(temp)/'job';job.mkdir();(job/'previews').mkdir()
            motion=job/'previews'/'short.motion.json'
            motion.write_text(json.dumps({'format':'dancerudiments.rig-motion','profile_sha256':'a'*64,
                'profile':{'channels':[],'source':{}},
                'recording':{'name':'sway','samples':[[] for _ in range(256)]}}))
            entry={'filename':'previews/short.motion.json','recording_sha256':preview._hash(motion),
                'source_bpm_estimated':120,'source_start_seconds':1,
                'source_end_seconds':3,'score':.9}
            (job/'job.json').write_text(json.dumps({'format':'dancerudiments.source-motion-loop-job',
                                                    'previews':[entry]}))
            # Stub sources implement canonical signature but never install/download.
            with patch.dict(sys.modules,{x:None for x in ('stemlab','stemlab.analysis','stemlab.analysis.loops','stemlab.types')}):
                for k in ('stemlab','stemlab.analysis','stemlab.analysis.loops','stemlab.types'):
                    sys.modules.pop(k,None)
                sys.path.insert(0,str(root/'src'))
                try:
                    with patch.object(preview,'SONGS',(('arcadians','examples/test/master.wav',
                                                       'examples/test/reference.json'),)),\
                         patch.object(preview,'_beat_grid',return_value={
                             'model':'test_grid','bpm':120,'beats':[i*.5 for i in range(16)],
                             'downbeats':[0,2,4,6],'beat_status':'synthetic',
                             'downbeat_status':'synthetic','meter_status':'synthetic'}):
                        result=preview.build(root,job,Path(temp)/'output',fail_on_song_error=True)
                finally:
                    sys.path.remove(str(root/'src'))
            self.assertEqual(len(result['songs']),1)
            self.assertEqual(result['songs'][0]['status'],'candidate_previews')
            self.assertEqual(len(result['songs'][0]['pairs']),1)
            index=Path(temp)/'output'/'index.html'
            self.assertTrue(index.exists())
            self.assertIn('preview-data',index.read_text())
            self.assertNotIn('%%PREVIEW_DATA%%',index.read_text())
            self.assertFalse(list((Path(temp)/'output').rglob('*.wav')))
            self.assertFalse(list((Path(temp)/'output').rglob('*.mp3')))
            self.assertEqual(result['songs'][0]['audio_loop_counts']['exploratory'],1)

if __name__=='__main__': unittest.main()
