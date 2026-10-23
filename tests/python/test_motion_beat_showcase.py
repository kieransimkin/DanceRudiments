"""Offline regression tests for CI skeleton preview selection and provenance."""
import importlib.util
from fractions import Fraction
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'tools'/'build_motion_beat_showcase.py'
spec = importlib.util.spec_from_file_location('motion_beat_showcase_tested', SCRIPT)
showcase = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = showcase
spec.loader.exec_module(showcase)


def synthetic_clip():
    rest=[]
    for name,parent,x,y,z in [('Hips',None,0,0,0),('Spine','Hips',0,0,1),
                              ('LeftArm','Spine',-.7,0,1.5),('RightArm','Spine',.7,0,1.5),
                              ('LeftFoot','Hips',-.3,0,-1),('RightFoot','Hips',.3,0,-1)]:
        mat=np.eye(4);mat[:3,3]=[x,y,z]
        rest.append({'name':name,'parent':parent,'rest_matrix':mat.reshape(-1).tolist()})
    channels=[]
    for bone in rest:
        for i in range(4):
            channels.append(SimpleNamespace(bone=bone['name'],data_path='rotation_quaternion',
                                            array_index=i,interpolation='quaternion'))
    n=240
    values=[]
    for i in range(n):
        t=i/30
        row=[]
        for j,bone in enumerate(rest):
            angle=0.5*np.sin(2*np.pi*t*2 + j*.4)
            row.extend((np.cos(angle/2),0,0,np.sin(angle/2)))
        values.append(row)
    return SimpleNamespace(
        frame_count=n, frame_time_seconds=Fraction(1,30),
        frames=np.asarray(values),profile=SimpleNamespace(
            source={'skeleton':rest},channels=channels))


def loop(score=.95,*,start=1,end=3,activity=None):
    return {'source_start_seconds':start,'source_end_seconds':end,'source_beats':4,
            'source_bpm_estimated':120,'score':score,
            'recording_sha256':'f'*64,'native_samples_verified':True,
            'requires_review':True,'loop_seam_approved':False,
            'audio_beat_alignment_verified':False,
            'stemlab_diagnostics':{'alignment':'estimated_motion_beat_grid',
                'pose_mismatch':.03,'velocity_mismatch':.04,'root_drift_relative':.001,
                'requires_review':True,'repaired':False}}


def test_reject_duplicate_sha_and_unknown_source():
    source={'files':[{'id':'a','sha256':'a'*64},{'id':'b','sha256':'a'*64}]}
    assert len(showcase.chosen_sources(source,['a']))==1
    try:
        showcase.chosen_sources(source,['a','b'])
        assert False
    except ValueError as e:
        assert 'Duplicate motion bytes' in str(e)
    try:
        showcase.chosen_sources(source,['unknown'])
        assert False
    except ValueError as e:
        assert 'Unknown unpinned' in str(e)


def test_motion_beat_selector_rejects_idle_and_bad_seams():
    live=np.ones(240)*.05
    inactive=live.copy();inactive[30:100]=.002
    result=showcase.pick_review_loops({'previews':[loop()]},live,frame_dt=1/30)
    assert len(result)==1 and result[0]['activity_relative_to_action']>0.9
    assert result[0]['beat_alignment_confirmed'] is False
    assert showcase.pick_review_loops({'previews':[loop()]}, inactive, frame_dt=1/30)==[]
    bad=loop();bad['stemlab_diagnostics']['root_drift_relative']=.2
    assert showcase.pick_review_loops({'previews':[bad]},live,frame_dt=1/30)==[]
    unverified=loop();unverified['native_samples_verified']=False
    assert showcase.pick_review_loops({'previews':[unverified]},live,frame_dt=1/30)==[]


def test_distinct_sources_and_short_loops_cannot_dominate():
    live=np.ones(240)*.05
    short=loop(start=.0,end=.4)
    duplicate=loop(start=1.1,end=3.1)
    selected=showcase.pick_review_loops({'previews':[short,loop(),duplicate]},live,frame_dt=1/30)
    assert len(selected)==1
    sources=[{'source_id':f'src_{i}','review_loops':[{'render_priority':v}]}
             for i,v in enumerate([.8,.9,.7])]
    sources[1]['review_loops'].append({'render_priority':.95})
    picked=showcase.select_showcase(sources,max_selected=3)
    assert [x['source_id'] for x,_ in picked]==['src_1','src_0','src_2']


def test_quaternion_sign_equivalence_and_pose_animation(tmp_path):
    clip=synthetic_clip()
    activity=showcase._quaternion_angular_motion(clip)
    flip=synthetic_clip();flip.frames[::2,4:8]*=-1
    equivalent=showcase._quaternion_angular_motion(flip)
    assert np.allclose(equivalent,activity,atol=1e-6)
    _,a=showcase.pose_joints(clip,0)
    _,b=showcase.pose_joints(clip,6)
    assert not np.allclose(a,b)
    candidate=loop()
    candidate['activity_relative_to_action']=.99
    candidate['beats_estimated']=4
    candidate['duration_seconds']=2
    candidate['start_seconds']=1
    candidate['end_seconds']=3
    # In test output, no original BVH or recording arrays are written.
    image=tmp_path/'rig.gif'
    showcase.make_preview_gif(clip,candidate,image,label='Synthetic 120 BPM',attribution='synthetic')
    with Image.open(image) as result:
        assert result.n_frames>=8 and result.size==(420,380)
    assert not (tmp_path/'source.motion.json').exists()


def test_gallery_has_attribution_and_review_labels(tmp_path):
    rows=[{'source_id':'103_03','title':'Charleston','source_url':'https://example.invalid/103',
           'review_loops':[]}]
    result={'start_seconds':1,'end_seconds':3,'duration_seconds':2,
            'beats_estimated':4,'source_bpm_estimated':120,
            'activity_relative_to_action':.8,'pose_mismatch':.1,
            'velocity_mismatch':.2,'root_drift_relative':.01}
    showcase.write_gallery(tmp_path,rows,[(rows[0],result)],mirror_commit='1'*40)
    html=(tmp_path/'index.html').read_text()
    assert 'CMU 103_03' in html and 'unverified' in html
    assert 'funding from NSF EIA-0196217' in html
    assert 'previews/103_03.gif' in html


@pytest.mark.parametrize("has_loops", [True, False])
def test_complete_showcase_build_with_pinned_stubbed_sources(tmp_path, monkeypatch, has_loops):
    """Integration of selection->source rig GIF->safe artifact without a download."""
    import hashlib
    import types
    repo = tmp_path / 'cache'
    ids = ['103_03', '106_12', '143_34']
    raws = {name: (name+'\n').encode() for name in ids}
    entries = [{'id': key, 'title': key+' synthetic',
                'cache_path': 'raw/'+key+'.bvh',
                'sha256': hashlib.sha256(raws[key]).hexdigest(),
                'source_url': 'https://example.invalid/'+key}
               for key in ids]
    def load_manifest(path):
        return {'files': entries, 'mirror_commit': '1'*40}
    def ensure_file(cache, item, *, download):
        assert not download
        dest = cache/item['cache_path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raws[item['id']])
    def load_bvh(path, *, source_id, axis_forward, axis_up, root_offset_policy):
        fake = synthetic_clip()
        fake.source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        fake.profile.fingerprint = 'a'*64
        fake.source_fps = 30.0
        fake.duration_seconds = 8.0
        return fake
    def source_capture_from_bvh(clip, *, calibration_frames, source_provenance):
        assert calibration_frames == 1
        return clip
    def analyze(captured, dest, *, original_source_sha256, **kwargs):
        assert kwargs['full_motion_confidence_threshold'] == .7
        assert kwargs['verify_native'] is True
        dest.mkdir(parents=True)
        return {'source_original_sha256': original_source_sha256,
                'profile_sha256': captured.profile.fingerprint,
                'full_motion_fit': {'selected_bpm': 120, 'confidence_percent': 60,
                                    'reasons': ['unverified_phase']},
                'full_motion_count': 0,
                'previews': [loop()] if has_loops else [],
                'unconverted_candidate_count': 0,
                'loopable_clip_count': int(has_loops)}
    imports = {
        'acquire_cmu_dance': types.SimpleNamespace(load_manifest=load_manifest, _ensure_file=ensure_file),
        'dancerudiments_authoring': types.ModuleType('dancerudiments_authoring'),
        'dancerudiments_authoring.bvh_import': types.SimpleNamespace(load_bvh=load_bvh),
        'dancerudiments_authoring.source_loop_analysis': types.SimpleNamespace(
            source_capture_from_bvh=source_capture_from_bvh,
            analyse_source_capture=analyze),
    }
    for name, value in imports.items():
        monkeypatch.setitem(sys.modules, name, value)
    output = tmp_path / 'safe_html'
    info = showcase.build(repo, output, ids=tuple(ids), download=False,
                          minimum_previews=3, max_selected=3)
    assert info['selected_source_count'] == 3
    assert info['selected_loop_candidate_count'] == (3 if has_loops else 0)
    assert info['selected_motion_study_count'] == (0 if has_loops else 3)
    assert len(list((output/'previews').glob('*.gif'))) == 3
    for name in ids:
        row = next(x for x in info['sources'] if x['source_id'] == name)
        assert row['source_id'] == info['sources'][ids.index(name)]['source_id']
        assert row['loop_seam_approved'] is False
        assert 'showcase_selection' in row
        assert ('showcase_loop' in row) == has_loops
    assert not list(output.glob('*.motion.json'))
    assert not list(output.glob('*.bvh'))
    assert (output/'index.html').exists() and (output/'summary.json').exists()
    try:
        showcase.build(repo, output, ids=tuple(ids), download=False)
        assert False
    except FileExistsError:
        pass


def test_fallback_motion_study_is_active_but_never_a_loop(tmp_path):
    motion = showcase._quaternion_angular_motion(synthetic_clip())
    study = showcase.pick_motion_study(
        motion, frame_dt=1/30, duration_seconds=8., source_bpm=117.)
    assert study is not None
    assert study['selection_kind'] == 'non_looping_motion_study'
    assert study['repeat_policy'] == 'do_not_repeat'
    assert study['native_samples_verified'] is False
    assert study['loop_seam_approved'] is False
    assert study['beats_estimated'] is None
    assert study['activity_relative_to_action'] >= .35
    assert study['moving_frame_fraction'] >= .35
    assert 1.5 <= study['duration_seconds'] <= 3.0
    path = tmp_path/'study.gif'
    showcase.make_preview_gif(synthetic_clip(), study, path,
                              label='Synthetic motion', attribution='synthetic')
    with Image.open(path) as gif:
        assert gif.n_frames >= 8 and gif.size == (420,380)
        assert 'loop' not in gif.info, 'Non-looping source study must not repeat forever'


def test_idle_motion_not_promoted_to_motion_study():
    assert showcase.pick_motion_study(np.zeros(240),frame_dt=1/30,duration_seconds=8) is None
    assert showcase.pick_motion_study(np.ones(240)*0.00001,frame_dt=1/30,
                                      duration_seconds=8) is None
    assert showcase.pick_motion_study(np.ones(240)*.03,frame_dt=1/30,
                                      duration_seconds=1.) is None


def test_loop_candidates_priority_then_diverse_nonloop_studies():
    study=lambda quality: {'selection_kind':'non_looping_motion_study',
                           'render_priority':quality}
    rows=[
        {'source_id':'a','title':'Charleston','review_loops':[], 'motion_study':study(.9)},
        {'source_id':'b','title':'Twist','review_loops':[], 'motion_study':study(.8)},
        {'source_id':'c','title':'Chicken Dance','review_loops':[{'render_priority':.1}],
         'motion_study':study(1.0)},
        {'source_id':'d','title':'Macarena','review_loops':[], 'motion_study':study(.6)},
    ]
    selected = showcase.select_showcase(rows, max_selected=4)
    assert len(selected)==4
    assert selected[0][0]['source_id']=='c', 'A real native-verified loop is prioritised'
    assert {row['source_id'] for row, _ in selected}=={'a','b','c','d'}
    assert len({row['source_id'] for row,_ in selected})==4


def test_study_gallery_declares_exactly_what_is_not_verified(tmp_path):
    study={'selection_kind':'non_looping_motion_study','duration_seconds':2.5,
           'activity_relative_to_action':1.2,'moving_frame_fraction':.7,
           'source_bpm_estimated':188.5}
    rows=[{'source_id':'143_35','title':'Macarena Dance',
           'source_url':'https://example.invalid','review_loops':[],
           'motion_study':study}]
    showcase.write_gallery(tmp_path,rows,[(rows[0],study)],mirror_commit='1'*40)
    html=(tmp_path/'index.html').read_text()
    assert 'Non-looping source-motion study' in html
    assert '0 unapproved loop candidates' in html
    assert '1 non-looping motion studies' in html
    assert 'native' not in html.lower() or 'native' not in html.split('Non-looping source-motion study')[1].split('</article>')[0]
    assert 'never original BVH' in html
