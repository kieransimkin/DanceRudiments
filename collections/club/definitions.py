"""Club Rhythms 05: inspectable drum scores, four original movement mappings.

Offline authoring only. Generated C++ tables are the playback authority.
Beat positions are exact rational QUARTER-NOTE beats, not seconds or MIDI ticks.
The Amen is a quantised structural study, NOT the original recording/groove map.
Other scores are illustrative genre studies, not exhaustive genre definitions.
"""
from __future__ import annotations
import math
from fractions import Fraction as F
from pathlib import Path
import json
from collections import defaultdict

COLLECTION_ID='club-05'
MAPPINGS=('bounce','step','orbit','glide')
LANES=('kick','snare','clap','hat','open_hat','ride','pedal_hat','rim','tom','shaker','bass','crash')
SOURCES=json.loads((Path(__file__).with_name('sources.json')).read_text())['sources']


def make(identifier,title,genre,bpm,bars,parts,*,swing=F(1,2),swing_lanes=('hat','shaker','rim'),references=(),note='',kind='original genre study'):
    events=[];length=F(bars*4)
    for lane,positions in parts.items():
        if lane not in LANES:raise ValueError(lane)
        for index,item in enumerate(positions):
            p,v=(item if isinstance(item,(tuple,list)) else (item,.85))
            # Input positions use 0-based sixteenth steps, optionally fractional.
            beat=F(str(p))/4
            if lane in swing_lanes and (beat*4).denominator==1 and int(beat*4)%2:
                beat-=F(1,4);beat+=F(swing)/2
            if not 0<=beat<length or not 0<v<=1:raise ValueError((identifier,lane,beat,v))
            events.append(dict(beat=str(beat),lane=lane,velocity=v,
                               note=([36,43,39,41][index%4] if lane=='bass' else 0)))
    events.sort(key=lambda e:(F(e['beat']),LANES.index(e['lane'])))
    keys=[(e['beat'],e['lane']) for e in events]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate same-lane onset: '+identifier)
    return dict(id=identifier,title=title,genre=genre,bpm=bpm,bars=bars,period_beats=str(length),
                meter=[4,4],beat_unit='quarter_note',swing_ratio=str(F(swing)),
                swing_applies_to=list(swing_lanes) if swing!=F(1,2) else [],
                reference_ids=list(references),interpretation=kind,notes=note,events=events)


def repeat(steps,bars,vel=.8):
    return [(F(str(p))+16*b,v) for b in range(bars) for p,v in
            [(x if isinstance(x,(tuple,list)) else (x,vel)) for x in steps]]


def rhythm_scores():
    out=[]
    def add(*args,**kwargs):out.append(make(*args,**kwargs))
    q=repeat([0,4,8,12],2,1);back=repeat([4,12],2,.9)
    h8=repeat([(i,.54 if i%4==0 else .38) for i in range(0,16,2)],2)
    h16=repeat([(i,.48 if i%4==0 else .24) for i in range(16)],2)
    oh=repeat([2,6,10,14],2,.62)
    add('four_floor','Four to the floor / bare pulse','Four to the floor',124,1,
        {'kick':[(i,1) for i in [0,4,8,12]]},references=['four_floor'],
        note='Equal quarter-note kicks only. This shared foundation is not itself a complete genre.')
    add('house_classic','House / kick-clap-offbeat hat','House',124,2,
        dict(kick=q,clap=back,open_hat=oh,hat=repeat([0,4,8,12],2,.32)),references=['four_floor','edm'])
    add('house_shuffle','House / shuffled hats','House',122,2,
        dict(kick=q,clap=back,hat=h16,open_hat=repeat([6,14],2,.52),rim=repeat([(7,.25),(15,.31)],2)),
        swing=F(3,5),references=['jack','four_floor'])
    add('house_jack','Jackin house / ghost-kick turnaround','House',126,2,
        dict(kick=q+[(7,.40),(30,.58)],clap=back+[(1,.22),(9,.24),(25,.25)],hat=h16,
             rim=[(11,.3),(23,.4),(31,.45)]),swing=F(2,3),references=['jack'],
        note='Original swung variant: extra ghost kicks and claps; not a transcription of a named track.')
    add('techno_drive','Techno / straight driving pulse','Techno',138,2,
        dict(kick=q,clap=back,hat=h16,open_hat=oh,ride=repeat([0,4,8,12],2,.23)),references=['techno','four_floor'])
    add('techno_toms','Techno / tom conversation','Techno',134,2,
        dict(kick=q,hat=h8,tom=[(3,.55),(6,.72),(11,.48),(18,.61),(23,.8),(29,.6)],
             clap=[(12,.65),(28,.68)]),references=['techno'])
    add('techno_broken','Techno / broken kick study','Techno',136,2,
        dict(kick=[0,6,10,16,19,24,30],rim=[4,12,20,28],hat=h16,
             tom=[(9,.4),(23,.5),(31,.35)]),references=['techno','edm'],
        note='A deliberately broken alternative; not all techno uses a quarter-note kick.')
    add('techno_polymeter','Techno / three-step percussion cycle','Techno',140,3,
        dict(kick=repeat([0,4,8,12],3,1),hat=repeat([2,6,10,14],3,.45),
             rim=[(i,.62 if i%9==0 else .35) for i in range(0,48,3)]),references=['techno'],
        note='Original three-sixteenth percussion cycle over 4/4: both layers close after three bars.')
    add('ukg_two_step','UK garage / two-step foundation','UK garage',132,2,
        dict(kick=repeat([0,10],2,1),snare=back,open_hat=repeat([2,6,14],2,.56),hat=repeat([(7,.32),(9,.3)],2)),
        swing=F(3,5),references=['garage'],note='Backbeats on 2/4; the second kick sits on the & of 3. Off-grid hats supply shuffle.')
    add('ukg_skip','UK garage / skipping answer','UK garage',132,2,
        dict(kick=[0,10,16,23,26],snare=back,hat=h16,open_hat=[6,14,22],rim=[(3,.4),(11,.5),(27,.34)]),
        swing=F(5,8),references=['garage'])
    add('ukg_four_four','UK garage / four-four shuffle','UK garage',130,2,
        dict(kick=q,snare=back,hat=h16,open_hat=oh,rim=[(7,.4),(19,.3),(31,.5)]),
        swing=F(2,3),references=['garage'],note='Garage also has a four-to-the-floor branch; it is not all two-step.')
    add('speed_garage','Speed garage / offbeat bass answers','UK garage',136,2,
        dict(kick=q,snare=back,hat=h16,open_hat=oh,bass=[2,7,10,15,18,22,27,30]),
        swing=F(3,5),references=['garage'],note='Bass onsets are included as movement cues. Audio uses a simple synth, not a sampled Reese patch.')
    add('bassline','Bassline / syncopated low-end hooks','Bassline',138,2,
        dict(kick=q,clap=back,hat=h8,open_hat=oh,bass=[2,3,6,11,14,18,21,22,27,31]),
        references=['garage','edm'])
    add('grime_sparse','Grime / sparse square-cut backbeat','Grime',140,2,
        dict(kick=[0,10,16,26],snare=back,hat=repeat([2,8,14],2,.42),rim=[(7,.55),(23,.5)]),references=['grime'])
    add('grime_syncopated','Grime / displaced snare conversation','Grime',140,2,
        dict(kick=[0,6,16,24,30],snare=[4,11,14,20,27],hat=[0,3,8,14,16,22,28],
             rim=[(7,.4),(18,.35),(31,.45)]),references=['grime'],
        note='A 140 BPM syncopated study; grime has no single mandatory snare pattern.')
    add('grime_half','Grime / half-time negative space','Grime',140,2,
        dict(kick=[0,14,16,23],snare=[8,24],hat=[2,6,11,18,22,29],rim=[(15,.38),(27,.5)],bass=[0,6,18,26]),
        references=['grime','edm'])
    drill_h=repeat([(0,.58),(3,.47),(6,.62),(8,.54),(11,.46),(14,.6)],2)
    add('drill_tresillo','UK drill / grouped hats','UK drill',144,2,
        dict(kick=[0,14,16,27],snare=[8,24],hat=drill_h,bass=[0,6,14,18,23,30]),references=['drill'],
        note='3+3+2 sixteenth grouping is not a tuplet: the grid here remains straight.')
    add('drill_displaced','UK drill / moving second-bar snare','UK drill',146,2,
        dict(kick=[0,14,16,23,30],snare=[8,28],hat=drill_h+[(15,.24)],bass=[0,7,14,16,23,30]),
        references=['drill'],note='Snare: beat 3 in bar one, beat 4 in bar two. This is one common design, not a rule for all drill.')
    add('drill_rolls','UK drill / true triplet hat fill','UK drill',144,2,
        dict(kick=[0,10,16,27],snare=[8,28],hat=drill_h+[(F(88,3),.25),(F(92,3),.31),(31,.24)],
             bass=[0,6,10,18,26,30]),references=['drill','grime'],
        note='The added hat fill uses rational tuplets; grouped hats and triplet rolls remain distinct concepts.')
    # Amen structural reference: opening bars identical; late 4& snares in bars 3/4.
    # Velocity values and straight timing are OUR approximation; no audio imported.
    amen_k=[(0,1),(2,.88),(10,.72),(11,.93),(16,1),(18,.88),(26,.72),(27,.93),
            (32,1),(34,.88),(42,.9),(50,.72),(51,.93),(58,.86)]
    amen_s=[(4,.96),(7,.35),(9,.42),(12,1),(15,.48),
            (20,.96),(23,.35),(25,.42),(28,1),(31,.48),
            (36,.96),(39,.35),(41,.42),(46,1),
            (49,.43),(52,.96),(55,.35),(57,.42),(62,1)]
    amen_r=[(i,.46) for i in range(0,64,2) if i!=58]
    amen=dict(kick=amen_k,snare=amen_s,ride=amen_r,pedal_hat=repeat([0,4,8,12],4,.12),crash=[(58,.75)])
    add('amen_four_bar','Amen / four-bar structural study','Amen & jungle',136,4,amen,
        references=['amen_lesson','amen_program'],kind='quantised structural interpretation',
        note='Gregory C. Coleman / The Winstons, Amen, Brother. Four bars, not a generic 2-bar loop. Timing/velocity are approximations; no original recording or measured human microtiming.')
    shell={k:v for k,v in amen.items()};shell['snare']=[(p,v) for p,v in amen_s if v>=.8]
    add('amen_no_ghosts','Amen / remove the ghost snares','Amen & jungle',136,4,shell,
        references=['amen_lesson','amen_program'],kind='educational reduction',
        note='A/B study: only quiet snares removed. This deliberately simplified version is not the complete Amen.')
    add('jungle_chops','Jungle / rearranged break fragments','Amen & jungle',168,2,
        dict(kick=[0,2,10,16,22,27],snare=[(4,1),(7,.38),(9,.45),(14,1),(20,1),(23,.34),(25,.46),(30,1),(31,.43)],ride=h8),
        references=['jungle','amen_program'],note='Original chopped-break-style arrangement, not the original Amen sequence.')
    add('jungle_ghosts','Jungle / ghosts and snare rolls','Amen & jungle',172,2,
        dict(kick=[0,2,10,11,16,26],snare=back+[(3,.25),(7,.34),(9,.4),(15,.28),(19,.26),(23,.37),(27,.4),(29,.3),(30,.48),(31,.6)],ride=h8),references=['jungle','amen_program'])
    add('jungle_switch','Jungle / full-time to half-time answer','Amen & jungle',170,4,
        dict(kick=[0,10,16,26,32,46,48,58],snare=[(4,1),(7,.3),(12,1),(20,1),(25,.4),(28,1),(40,1),(55,.33),(56,1),(62,.4),(63,.3)],
             ride=repeat(range(0,16,2),4,.48)),references=['jungle','edm'],note='Four-bar original phrase: the final half uses fewer main snares, not a tempo change.')
    add('dnb_two_step','Drum & bass / two-step foundation','Drum & bass',174,2,
        dict(kick=repeat([0,10],2,1),snare=back,hat=h8),references=['dnb'])
    add('dnb_rolling','Drum & bass / rolling ghosts','Drum & bass',174,2,
        dict(kick=[0,10,16,26,30],snare=back+[(7,.32),(9,.4),(23,.28),(25,.38),(31,.35)],hat=h16,
             open_hat=[(14,.54),(22,.48)]),swing=F(11,20),references=['dnb'])
    add('dnb_half','Drum & bass / half-time space','Drum & bass',172,2,
        dict(kick=[0,6,16,30],snare=[8,24],hat=h8,rim=[(3,.4),(15,.3),(23,.4)],bass=[0,10,18,26]),references=['dnb','edm'])
    add('dubstep_half','Dubstep / half-step anchor','Dubstep',140,2,
        dict(kick=[0,16,27],snare=[8,24],hat=[(2,.3),(6,.4),(14,.5),(18,.3),(22,.4),(30,.5)],bass=[0,4,11,16,20,28]),references=['edm'])
    add('dubstep_skip','Dubstep / skippy half-step','Dubstep',140,2,
        dict(kick=[0,6,16,22,30],snare=[8,24],hat=h16,rim=[(3,.4),(15,.42),(19,.4),(27,.42)],bass=[2,11,18,28]),swing=F(3,5),references=['edm','garage'])
    add('trap_trills','Trap / half-time and hat trills','Trap',140,2,
        dict(kick=[0,7,14,16,22,29],snare=[8,24],hat=h8+[(F(43,3),.28),(F(44,3),.35),(F(46,3),.38),(F(47,3),.42),(F(61,2),.26),(31,.32),(F(63,2),.4)],
             bass=[0,7,16,22,29]),references=['grime'])
    add('electro','Electro / broken machine groove','Electro',128,2,
        dict(kick=[0,6,10,16,19,26],snare=back,hat=h16,open_hat=[(14,.58),(30,.54)],rim=[(3,.4),(22,.4)]),references=['edm'])
    add('trance','Trance / offbeat lift','Trance',138,2,
        dict(kick=q,clap=back,hat=h16,open_hat=oh,bass=repeat([2,6,10,14],2,.72)),references=['edm','four_floor'],
        note='Offbeat bass/pulse is included. A rhythmic sketch cannot supply trance harmony, timbre or arrangement.')
    add('rave_breaks','Rave / four-floor plus break layer','Breakbeat',144,2,
        dict(kick=q+[(10,.52),(27,.44)],snare=back+[(7,.3),(9,.42),(15,.4),(23,.35),(25,.37),(31,.46)],ride=h8),references=['rave'])
    add('dembow','Reggaeton / dembow answer','Reggaeton',96,2,
        dict(kick=q,snare=repeat([3,6,11,14],2,.88),hat=h8),references=['dembow'],
        note='Quarter-note kick version with offbeat snare answers; one useful dembow foundation, not every dancehall rhythm.')
    add('disco','Disco / lively hat accents','Disco',118,2,
        dict(kick=q,snare=back,hat=h16,open_hat=repeat([6,14],2,.66),shaker=repeat([1,5,9,13],2,.23)),swing=F(11,20),references=['disco','four_floor'])
    add('amapiano','Amapiano / shaker and bass-percussion study','Amapiano',112,2,
        dict(kick=repeat([0,4,8,12],2,.74),rim=[(6,.6),(14,.58),(22,.64),(30,.58)],shaker=h16,
             open_hat=[(10,.42),(26,.42)],bass=[3,6,11,15,18,23,26,30]),swing=F(29,50),references=['amapiano'],
        note='An original percussion and log-drum-style bass rhythm. Pitched bass is a cue lane, not a downloaded sample.')
    if len(out)!=36:raise ValueError('Unexpected rhythm count '+str(len(out)))
    return out


def envelope(distance,attack,release):
    """C1 cosine packet: maximum at the musical event, resting at both ends."""
    if distance<0:return .5+.5*math.cos(math.pi*distance/attack) if distance>=-attack else 0.
    return .5+.5*math.cos(math.pi*distance/release) if distance<=release else 0.


def bake_motion(rhythm,mapping):
    period=F(rhythm['period_beats']);n=int(period*64);length=float(period)
    events=rhythm['events'];channels=defaultdict(lambda:[0.]*n);signed=defaultdict(lambda:[0.]*n)
    attacks={'kick':.10,'snare':.09,'clap':.10,'hat':.075,'open_hat':.09,'ride':.07,'pedal_hat':.07,
             'rim':.08,'tom':.11,'shaker':.07,'bass':.15,'crash':.15}
    release={'kick':.46,'snare':.32,'clap':.36,'hat':.14,'open_hat':.28,'ride':.17,'pedal_hat':.14,
             'rim':.20,'tom':.38,'shaker':.12,'bass':.8,'crash':.8}
    counts=defaultdict(int)
    for e in events:
        lane=e['lane'];sign=1 if counts[lane]%2==0 else -1;counts[lane]+=1
        time=float(F(e['beat']));a=attacks[lane];b=release[lane]
        # Convert the rational onset only at the final envelope-sampling boundary.
        for pip in range(n):
            d=pip/64-time
            # Enclosing cyclic interval; no running PRNG/filter state.
            value=sum(envelope(d+j*length,a,b) for j in (-1,0,1))*e['velocity']
            channels[lane][pip]+=value;signed[lane][pip]+=sign*value
    c=lambda lane,i:channels[lane][i]
    z=lambda lane,i:signed[lane][i]
    # Positive periodic angular speed from beat activity: no backwards phase/reset.
    weights=[.18+.6*c('kick',i)+.45*(c('snare',i)+c('clap',i))+.10*c('hat',i)+.10*c('bass',i) for i in range(n)]
    total=sum(weights);angles=[];acc=0.
    for value in weights:angles.append(2*math.pi*acc/total);acc+=value
    raw=[]
    for i in range(n):
        k=c('kick',i);s=c('snare',i)+c('clap',i);h=c('hat',i)+.8*c('open_hat',i)+.55*c('ride',i)+.5*c('shaker',i)+.3*c('pedal_hat',i)
        t=c('tom',i)+c('rim',i);b=c('bass',i);xsn=z('snare',i)+z('clap',i);a=angles[i]
        if mapping=='bounce':row=(.27*xsn+.08*z('rim',i),.55*k-.22*s-.045*h,.045*z('bass',i)+.08*c('crash',i))
        elif mapping=='step':row=(.42*z('kick',i)-.32*xsn+.08*z('hat',i)+.10*z('tom',i),-.22*k-.14*s+.09*h,.12*b-.07*c('crash',i))
        elif mapping=='orbit':
            radius=.43+.15*k-.07*s+.04*t
            row=(radius*math.cos(a),radius*math.sin(a),.16*xsn+.045*h-.11*b+.08*c('crash',i))
        else:
            # A lower-frequency continuous spine plus audible event-shaped excursions.
            row=(.40*math.sin(a)+.20*z('bass',i)+.13*z('kick',i),.26*math.sin(2*a)-.21*s-.075*h,
                 .27*math.cos(a)+.17*b-.13*k+.08*t+.08*c('crash',i))
        raw.append(row)
    peak=max(abs(v) for row in raw for v in row)
    gain=min(1.,.9/peak)
    samples=[tuple(round(v*gain,12) if abs(v*gain)>=.5e-12 else 0. for v in row) for row in raw]
    if max(math.dist(samples[i-1],samples[i]) for i in range(n))>.35:raise ValueError('Excessive step '+rhythm['id'])
    return samples,gain


def document():
    result=[]
    labels={'bounce':'Kick-led bounce','step':'Snare side-step','orbit':'Percussion orbit','glide':'Bass-and-phrase glide'}
    for rhythm in rhythm_scores():
        for mapping in MAPPINGS:
            samples,gain=bake_motion(rhythm,mapping)
            result.append(dict(name='beat_'+rhythm['id']+'_'+mapping,
                description=rhythm['title']+' — '+labels[mapping]+'. '+rhythm['notes'],
                period_beats=rhythm['period_beats'],loop_policy='closed',bounds='reject',
                tracks=[dict(axis=axis,curve=dict(type='samples',values=[s[j] for s in samples],
                        period_beats=rhythm['period_beats'],interpolation='linear')) for j,axis in enumerate('xyz')],
                provenance=dict(collection_id=COLLECTION_ID,title=rhythm['title']+' / '+labels[mapping],
                    family=rhythm['genre'],author='Kieran Simkin / DanceRudiments',license='MIT',
                    source_kind=rhythm['interpretation'],source_url='https://github.com/kieransimkin/DanceRudiments',
                    reference_urls=[SOURCES[key]['url'] for key in rhythm['reference_ids']],
                    rhythm_id=rhythm['id'],mapping=mapping,bpm=rhythm['bpm'],beat_unit='quarter_note',
                    swing_ratio=rhythm['swing_ratio'],event_anchor='envelope peak at exact musical onset',
                    event_markers=[dict(beat=e['beat'],lane=e['lane'],velocity=e['velocity']) for e in rhythm['events']],
                    parameters=dict(uniform_gain=gain,position_resolution=64),
                    interpretation_notes=rhythm['notes'],
                    transformation='New abstract positional mapping; no recorded audio, choreography, groove-template extraction or factory presets.')))
    return dict(format='dancerudiments.score-pack',schema_version=1,patterns=result)
