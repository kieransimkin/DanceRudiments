"""Original scores and explicitly attributed source conversions for Initial 01.

No runtime playback functions: the results are baked by the existing compiler.
D3-derived functions below retain the BSD-3-Clause notice in sources/d3-ease/LICENSE.
"""
from __future__ import annotations

import base64
from fractions import Fraction
from hashlib import sha256
import math
from pathlib import Path

from dancerudiments_authoring.initial_sources import (verify_blob, read_akwf_header,
    smooth_periodic, read_midi, excerpt_hits)

HERE = Path(__file__).resolve().parent
COLLECTION_ID = 'initial-01'
PROJECT_URL = 'https://github.com/kieransimkin/DanceRudiments'


def ratio(value):
    return str(Fraction(value))


def osc(period=4, gain=.8, phase=0, shape='sine', **extra):
    return dict(type='lfo', shape=shape, period_beats=ratio(period),
                phase=ratio(phase), gain=gain, **extra)


def keys(points):
    return dict(type='keyframes', points=[dict(beat=ratio(b), value=v,
                      interpolation='smootherstep') for b, v in points])


def samples(values, period=4, gain=1):
    return dict(type='samples', values=list(values), period_beats=ratio(period),
                gain=gain, interpolation='linear')


def original(family, title, notes, **extra):
    return dict(collection_id=COLLECTION_ID, title=title, family=family,
                author='Kieran Simkin / DanceRudiments', license='MIT',
                source_url=PROJECT_URL, source_kind='original',
                transformation=notes, **extra)


def score(name, title, family, desc, period=4, axes=None, events=None, gestures=None,
          provenance=None, **meta):
    return dict(name=name, description=desc, period_beats=ratio(period),
                tracks=[dict(axis=a, curve=c) for a,c in (axes or {}).items()],
                events=events or [], gestures=gestures or {}, bounds='scale',
                loop_policy='closed', provenance=provenance or original(family,title,desc,**meta))


def gesture(x=0, y=0, duration=Fraction(3, 8)):
    return dict(duration_beats=ratio(duration), axes=dict(x=x,y=y),
                peak_fraction='1/2', shape='cosine')


def event(beat, key='hit', strength=1, duration=None):
    result = dict(beat=ratio(beat), gesture=key, strength=strength, anchor='peak')
    if duration is not None:
        result['duration_beats'] = ratio(duration)
    return result


def original_scores():
    s=[]
    s.append(score('lfo_breathe','Breathe','LFO',
        'A four-beat, single-axis sine. The quiet reference for judging busier shapes.',
        axes={'x':osc()}))
    s.append(score('lfo_surge','Surge & recover','LFO',
        'A long rounded sweep and short recovery; an independently authored smooth-reset shape.',
        axes={'x':keys([(0,-.8),(3,.8),(4,-.8)])}))
    s.append(score('lfo_soft_gate','Soft gate','LFO',
        'Short smooth transitions separated by long stationary dwells. No square-wave teleport.',
        axes={'x':keys([(0,-.8),(Fraction(1,2),.8),(2,.8),(Fraction(5,2),-.8),(4,-.8)])}))
    s.append(score('lfo_double_pump','Double pump','LFO',
        'Two unequal pumps and a breathing space within four beats.',
        axes={'y':keys([(0,0),(Fraction(1,2),-.85),(1,0),(Fraction(3,2),-.55),
                        (2,0),(4,0)])}))
    s.append(score('lfo_ratchet','Ratchet & release','LFO',
        'A four-hit decaying burst, then a rest. Every event is peak-aligned.',
        events=[event(Fraction(i,4),'hit',1-.18*i) for i in range(4)],
        gestures={'hit':gesture(.8,-.5,Fraction(1,4))}))
    s.append(score('lfo_glide_stair','Glide staircase','LFO',
        'Five rounded steps traverse the field, then a smooth return.',
        axes={'x':keys([(0,-.8),(Fraction(1,2),-.8),(1,-.4),(Fraction(3,2),0),
                (2,.4),(Fraction(5,2),.8),(3,.8),(4,-.8)])}))
    s.append(score('lfo_morph','Morphing wobble','LFO',
        'An eight-beat blend between a sine and skewed triangle; movement changes within the phrase.',8,
        axes={'x':dict(type='mix',a=osc(2,.8),b=osc(2,.8,shape='skew_triangle',duty=.23),
                       amount=osc(8,.5,phase=Fraction(-1,4),offset=.5)),
              'y':osc(8,.2)}))
    s.append(score('lfo_flower','Three-lobe orbit','LFO',
        'Related rotations form an original three-lobed XY loop over eight beats.',8,
        axes={'x':dict(type='sum',curves=[osc(8,.56,Fraction(1,4)),osc(4,.28,Fraction(-1,4))]),
              'y':dict(type='sum',curves=[osc(8,.56),osc(4,.28)])}))
    for pulses, steps in [(3,8),(5,12)]:
        mask=[i for i in range(steps) if (i*pulses)%steps < pulses]
        es=[event(Fraction(i*4,steps),'right' if j%2==0 else 'left') for j,i in enumerate(mask)]
        s.append(score(f'rhythm_euclid_{pulses}_{steps}',f'{pulses} in {steps}','Rhythm',
            f'{pulses} evenly distributed onsets on a {steps}-step grid. Alternating lateral gestures.',
            events=es,gestures={'right':gesture(.8,-.3),'left':gesture(-.8,-.3)},
            algorithm='onset where (step * pulses) % steps < pulses; four-quarter-note loop'))
    s.append(score('rhythm_three_two','Three against two','Rhythm',
        'Three horizontal gestures interlock with two vertical gestures in one four-beat cycle.',
        events=[event(Fraction(4*i,3),'side') for i in range(3)]+
               [event(i*2,'down') for i in range(2)],
        gestures={'side':gesture(.78,0,Fraction(3,4)), 'down':gesture(0,.78,Fraction(3,4))}))
    s.append(score('rhythm_half_time','Half-time lurch','Rhythm',
        'A strong downbeat, snare-like accent on beat three, and smaller offbeat shuffles.',
        events=[event(0,'kick'),event(Fraction(3,2),'kick',.55),event(2,'snare'),
                event(Fraction(7,2),'side',.5)],
        gestures={'kick':gesture(0,.85,Fraction(1,2)), 'snare':gesture(.85,-.25,Fraction(1,2)),
                  'side':gesture(-.8,-.2,Fraction(3,8))}))
    # Independently authored sticking studies, not copied notation or audio.
    for name,title,sticking,accents in [
        ('rudiment_double_paradiddle','Double paradiddle study','RLRLRRLRLRLL',{0,6}),
        ('rudiment_paradiddle_diddle','Paradiddle-diddle study','RLRRLLLRLLRR',{0,6}),
        ('rudiment_six_stroke','Six-stroke study','RLLRRLLRRLLR',{0,5,6,11})]:
        es=[event(Fraction(i,3),'right' if hand=='R' else 'left',1 if i in accents else .6,
                  Fraction(7,24)) for i,hand in enumerate(sticking)]
        s.append(score(name,title,'Rudiment',
             f'Visual sticking study {sticking[:6]} {sticking[6:]}; equal triplet spacing over four beats. '
             'This is a movement interpretation, not a complete drum-performance notation.',
             events=es,gestures={'right':gesture(.82,-.42), 'left':gesture(-.82,-.42)},
             sticking=sticking, spacing_beats='1/3', accented_indices=sorted(accents)))
    es=[]
    for i,hand in enumerate('RLRLRL'):
        t=Fraction(2*i,3)
        key='right' if hand=='R' else 'left'
        es.append(event(t,key,1 if i%3==0 else .6,Fraction(1,2)))
        if i%3==0:
            es.append(event((t-Fraction(1,8))%4,'left' if hand=='R' else 'right',.32,Fraction(1,4)))
    s.append(score('rudiment_flam_accent','Flam accent study','Rudiment',
        'Opposite-hand grace gestures lead accented groups of three; deliberately expanded for visible motion.',
        events=es,gestures={'right':gesture(.82,-.42),'left':gesture(-.82,-.42)},
        timing_note='Main strokes every 2/3 quarter-note beat; grace 1/8 beat before each accented lead.'))
    return s


# Adapted from d3/d3-ease src/bounce.js and src/back.js. BSD-3-Clause;
# Copyright 2010-2021 Mike Bostock; Copyright 2001 Robert Penner.
def bounce_out(t):
    b0=1/(4/11)**2
    if t < 4/11: return b0*t*t
    if t < 8/11: return b0*(t-6/11)**2+3/4
    if t < 10/11: return b0*(t-9/11)**2+15/16
    return b0*(t-21/22)**2+63/64


def back_in(t):
    return t*t*(1.70158*(t-1)+t)


def back_out(t):
    t-=1
    return t*t*((t+1)*1.70158+t)+1


def easing_scores():
    result=[]
    notice=(HERE/'sources/d3-ease/LICENSE').read_text(encoding='utf-8')
    verify_blob(notice.encode(), '83cc9970536d2b2bd0fa53ae1b0a94f378cf8fb4')
    for name,title,fn,source,blob in [
        ('ease_rebound','Rebound',bounce_out,'bounce.js','d2d81caf0193c48fa903bb02f0edef00be260a07'),
        ('ease_anticipate','Anticipation',back_in,'back.js','b9c1bcc90eaaa8f39d9eeee2894857f60c5b3633'),
        ('ease_overshoot','Overshoot & settle',back_out,'back.js','b9c1bcc90eaaa8f39d9eeee2894857f60c5b3633')]:
        values=[]
        for i in range(256):
            p=i/256
            u=2*p if p<.5 else 2*p-1
            v=fn(u) if p<.5 else 1-u*u*(3-2*u)
            values.append(-.65+1.3*v)
        prov=dict(collection_id=COLLECTION_ID,title=title,family='Easing',source_kind='adapted-code',
                  author='Mike Bostock; Robert Penner',license='BSD-3-Clause',license_notice=notice,
                  source_url=f'https://github.com/d3/d3-ease/blob/main/src/{source}',
                  source_blob_sha1=blob,transformation='Offline Python port of the D3 easing equation; '
                  'two-beat outward ease followed by two-beat smoothstep return. 256-sample periodic table.')
        result.append(score(name,title,'Easing','An attributed D3 easing curve, assembled into a closed outward-and-return loop.',
                            axes={'x':samples(values)},provenance=prov))
    vals=[]
    for i in range(256):
        p=i/256
        # Original windowed ringing; value and slope close at the cycle boundary.
        vals.append(.85*math.sin(2*math.pi*3*p)*(math.sin(math.pi*p)**2)*math.exp(-2*p))
    peak=max(abs(x) for x in vals)
    vals=[v*.8/peak for v in vals]
    result.append(score('ease_elastic','Elastic ring','Easing',
         'Original windowed, decaying oscillation; not a copied D3 curve. Peak scaled to .8.',
         axes={'x':samples(vals)}))
    return result


AKWF_FILES=[
 ('AKWF_R_asym_saw_05_256.h','AKWF_bw_sawrounded','3f35422b9b56f89b1d2595213a41c1690cad0ac1','akwf_round_saw','AKWF / rounded saw'),
 ('AKWF_R_asym_saw_15_256.h','AKWF_bw_sawrounded','6e1c29e672d223e5531c1965ada2d9fd6d9a53b8','akwf_quick_return','AKWF / quick return'),
 ('AKWF_0001_256.h','AKWF_0001','b1964a2d21af72cc0c9036fd41a53c9570b4705c','akwf_multi_lobe','AKWF / multiple lobes'),
 ('AKWF_0010_256.h','AKWF_0001','11120003877cbac456a51f5798acaa7aa6ab05ee','akwf_plateau','AKWF / plateau')]


def akwf_scores():
    result=[]
    for filename,folder,blob,name,title in AKWF_FILES:
        raw=(HERE/'sources/akwf'/filename).read_bytes()
        digest=verify_blob(raw,blob)
        data=smooth_periodic(read_akwf_header(raw),passes=8)
        prov=dict(collection_id=COLLECTION_ID,title=title,family='AKWF',source_kind='imported-waveform',
          author='Kristoffer Karl Axel Ekstrand (Adventure Kid); Teensy conversion by Marcelo Valeria',
          license='CC0-1.0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',
          source_url=f'https://github.com/KristofferKarlAxelEkstrand/AKWF-FREE/blob/main/AKWF--Teensy/{folder}/{filename}',
          source_blob_sha1=blob,source_sha256=digest,
          transformation='256 int16 source samples; eight circular [1/4,1/2,1/4] smoothing passes; '
             'subtract DC mean; scale peak to .85; linearly resample over four quarter-note beats. '
             'No factory synthesizer preset used.')
        result.append(score(name,title,'AKWF',f'{filename}: an actual CC0 waveform slowed to a four-beat position loop.',
                    axes={'x':samples(data)},provenance=prov))
    return result


GMD_BLOB='4d4889860dea1b6ed9b65ee395aff3eb75c76ad1'
GMD_MIRROR='https://github.com/florento/MEI-GMD/blob/main/D1S1_001/1_funk_80_beat_4-4.mid'
DRUM_MAP={36:'kick',38:'snare',40:'snare',37:'snare',48:'high_tom',50:'high_tom',
 45:'mid_tom',47:'mid_tom',43:'low_tom',58:'low_tom',46:'hat',26:'hat',42:'hat',22:'hat',
 44:'pedal',49:'cymbal',55:'cymbal',57:'cymbal',52:'cymbal',51:'cymbal',59:'cymbal',53:'cymbal'}


def groove_scores():
    encoded=(HERE/'sources/groove/1_funk_80_beat_4-4.mid.b64').read_bytes()
    raw=base64.b64decode(b''.join(encoded.split()), validate=True)
    digest=verify_blob(raw,GMD_BLOB)
    midi=read_midi(raw)
    if midi.ppq != 480 or midi.tempos != ((0,750000),) or midi.meters != ((0,4,4),):
        raise ValueError('Unexpected timing metadata in pinned Groove source')
    result=[]
    for letter,start in [('a',4),('b',36)]:
        for quantise in (False,True):
            es=[]; markers=[]
            for beat,hit in excerpt_hits(midi,start,8,quantise):
                key=DRUM_MAP.get(hit.note)
                if key is None:
                    raise ValueError(f'Unknown Groove drum note {hit.note}')
                if key=='pedal':
                    continue
                es.append(event(beat,key,hit.velocity/127))
                markers.append(dict(beat=ratio(beat),note=hit.note,velocity=hit.velocity,gesture=key))
            timing='grid' if quantise else 'played'
            title=f'Groove {letter.upper()} / '+('16th grid' if quantise else 'played')
            prov=dict(collection_id=COLLECTION_ID,title=title,family='Groove MIDI',source_kind='imported-events',
              author='Google LLC / Groove MIDI Dataset; anonymous drummer 1, session 1',
              license='CC-BY-4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
              attribution='Groove MIDI Dataset (GMD), Google LLC; Gillick, Roberts, Engel, Eck and Bamman (2019), Learning to Groove with Inverse Sequence Transformations.',
              source_url='https://magenta.withgoogle.com/datasets/groove',
              retrieved_from=GMD_MIRROR,source_blob_sha1=GMD_BLOB,source_sha256=digest,
              source_file='1_funk_80_beat_4-4.mid',source_ppq=480,source_bpm=80,
              excerpt_start_beat=start,excerpt_length_beats=8,timing=timing,
              paired_with=f'groove_{letter}_'+('played' if quantise else 'grid'),
              event_markers=markers,
              transformation='Original MIDI retrieved from the MEI-GMD mirror, not its MEI transcriptions. '
                'Nearest-sixteenth ownership selects the same eight-beat excerpt in both variants, including anticipatory hits. '
                + ('Original tick/480 timestamps retained as exact fractions, modulo the loop. ' if not quantise else
                   'Timestamp quantisation to nearest quarter-beat (16th note), ties towards +infinity. No event merging. ')
                + 'Velocities retained /127. Pedal note 44 and MIDI controllers omitted. '
                'Note-ons align gesture peaks. Kick=down, snare=right/up, hats=small left/up, '
                'toms=lateral, cymbals=up. Gesture vectors scaled by 1.6 before shared bounds=scale. '
                'This is an invented visual mapping, not captured body movement; no source audio is included.')
            gs={'kick':gesture(0,1.6,Fraction(1,2)),
                'snare':gesture(1.6,-.45,Fraction(3,8)),
                'hat':gesture(-.5,-.24,Fraction(1,4)),
                'high_tom':gesture(1.25,-.4,Fraction(3,8)),
                'mid_tom':gesture(0,-1.4,Fraction(3,8)),
                'low_tom':gesture(-1.4,-.4,Fraction(3,8)),
                'cymbal':gesture(-.6,-1.4,Fraction(1,2))}
            result.append(score(f'groove_{letter}_{timing}',title,'Groove MIDI',
              f'Two-bar funk excerpt {letter.upper()} ({start}–{start+8} source beats), '+
              ('performed microtiming.' if not quantise else 'same hits quantised to sixteenths.'),
              8,events=es,gestures=gs,provenance=prov))
    return result


def document():
    return dict(format='dancerudiments.score-pack',schema_version=1,
                patterns=original_scores()+easing_scores()+akwf_scores()+groove_scores())
