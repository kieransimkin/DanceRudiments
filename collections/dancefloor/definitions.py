"""Dancefloor 06: researched rhythm studies and twelve new motion interpretations.

Authoring only. The emitted C++ sample tables, not this Python code, do playback.
Rhythm positions are rational quarter-note beats. All extra accompaniments are
original illustrative arrangements, never sample-exact commercial transcriptions.
"""
from __future__ import annotations
from fractions import Fraction as F
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('dancefloor_club05', ROOT/'collections/club/definitions.py')
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
COLLECTION_ID = 'dancefloor-06'
MAPPING_VERSION = 1
MAPPINGS = (
    'bounce', 'step', 'orbit', 'glide', 'surge', 'recoil', 'flutter', 'dive',
    'pendulum', 'figure8', 'box', 'corkscrew', 'spiral', 'slalom', 'spring', 'ricochet')
MAPPING_INFO = {
    'bounce': ('Kick-led bounce', 'Original Club 05 kick-led downstroke and side accents.', 'anticipatory peak'),
    'step': ('Snare side-step', 'Original Club 05 alternating lateral kick and snare gestures.', 'anticipatory peak'),
    'orbit': ('Percussion orbit', 'Original Club 05 event-weighted orbital speed, radius and depth.', 'phase modulation'),
    'glide': ('Bass / phrase glide', 'Original Club 05 continuous phrase path with bass excursions.', 'mixed'),
    'surge': ('Forward surge', 'Kick thrust through depth with contrasting snare lift and hat detail.', 'anticipatory peak'),
    'recoil': ('Backbeat recoil', 'Snare pushes sideways; kick counters downward; delayed echo draws back.', 'peak and delayed response'),
    'flutter': ('Upper-percussion flutter', 'Hat and shaker tremors over a wider kick/snare arc.', 'anticipatory peak'),
    'dive': ('Bass-led dive', 'Bass drives a broad depth plunge with alternating drum counterweight.', 'anticipatory peak'),
    'pendulum': ('Weighted pendulum', 'A hanging arc whose amplitude and angular speed respond to the score.', 'phase modulation'),
    'figure8': ('Woven figure eight', 'Two crossing lobes expand at kicks with a lifted snare crossing.', 'phase modulation'),
    'box': ('Rounded corner tour', 'Rhythm-weighted phase travels around four softened corners.', 'phase modulation'),
    'corkscrew': ('Closed corkscrew', 'Two orbital turns ride a depth wave with percussion-driven radius.', 'phase modulation'),
    'spiral': ('Breathing spiral', 'A contracting and expanding double-turn path with a continuous seam.', 'phase modulation'),
    'slalom': ('Drum slalom', 'S-shaped travel with kick lift, snare cutbacks and depth counter-motion.', 'mixed'),
    'spring': ('Causal spring', 'An event starts at rest, then drives a damped ringing excursion.', 'causal onset; peaks after hit'),
    'ricochet': ('Directional ricochet', 'Successive onsets send smooth excursions toward a cyclic series of targets.', 'anticipatory peak'),
}
LANES = legacy.LANES
make, repeat = legacy.make, legacy.repeat


def new_rhythms():
    """32 original studies. Foundation claims are scoped individually in sources.json."""
    out = []
    def add(i, title, family, bpm, parts, refs, note, swing=F(1,2)):
        out.append(make(i, title, family, bpm, 2, parts, swing=swing,
                        references=refs, note=note,
                        kind='original arrangement using documented rhythmic features'))
    q = repeat([0,4,8,12],2,1)
    back = repeat([4,12],2,.82)
    h8 = repeat([(i,.43 if i%4==0 else .30) for i in range(0,16,2)],2)
    h16 = repeat([(i,.42 if i%4==0 else .22) for i in range(16)],2)
    off = repeat([2,6,10,14],2,.56)
    jersey = repeat([0,4,8,11,14],2,1)
    add('jersey_five','Jersey / five-kick foundation','Jersey club',142,
        dict(kick=jersey,snare=[(8,.80),(11,.75),(24,.83),(27,.78)],hat=back),['jersey'],
        'Kick on zero-based sixteenths 0,4,8,11,14: two quarters then 3+3+2 sixteenths. Not triplets. Accompaniment is authored.')
    add('jersey_call','Jersey / call and turnaround','Jersey club',144,
        dict(kick=jersey,snare=[8,11,24,27,(26,.35)],clap=[4,20],hat=off,
             bass=[(0,.70),(11,.55),(16,.72),(27,.55)],rim=[(2,.5),(6,.4),(18,.5),(19,.28),(22,.44)]),['jersey'],
        'Same signature kick cycle, original two-bar response and quiet snare pickup; not a new canonical kick pattern.')
    add('footwork_triplet','Footwork / triplet bass reply','Footwork',160,
        dict(kick=[0,6,16,26,30],snare=[8,24],clap=[4,12,20,28],hat=h8,
             bass=[0,F(8,3),F(16,3),12,16,F(56,3),F(64,3),28]),['footwork'],
        'Authored sparse drum/bass conversation. Bass replies include genuine thirds of a beat; not a genre-wide transcription.')
    add('footwork_sparse','Footwork / interrupted half-time','Footwork',160,
        dict(kick=[0,3,10,16,22,27],snare=[8,24],hat=[0,2,6,8,10,14,16,18,20,26,28,30],
             rim=[(5,.55),(13,.5),(21,.55),(29,.6)],bass=[0,6,11,16,23,30]),['footwork'],
        'An original interrupted 808-style study; the suggested tempo is an audition setting, not a classification rule.')
    add('funky_toms','UK funky / tom-led skips','UK funky',130,
        dict(kick=[0,4,8,12,16,20,26,28],clap=back,hat=off,
             tom=[(3,.58),(6,.76),(11,.56),(18,.63),(23,.82),(29,.65)],bass=[0,7,16,27]),['roska'],
        'Tom/rim motion is an original response to Roska’s discussion of skippy, travelling percussion, not one of his tracks.')
    add('funky_syncopated','UK funky / broken response','UK funky',132,
        dict(kick=[0,6,8,14,16,20,26,30],snare=[4,12,20,28],hat=h8,
             rim=[3,7,10,15,18,23,27,31],tom=[(5,.45),(22,.55)],bass=[0,10,18,26]),['roska'],
        'Kick gaps and percussion answers produce a different phrase without applying swing to the main anchors.')
    add('broken_push','Broken beat / early-and-late answers','Broken beat',124,
        dict(kick=[0,7,10,16,22,27],snare=[4,14,20,28],hat=h8,
             rim=[(3,.45),(11,.55),(19,.48),(30,.6)],tom=[(9,.44),(25,.5)],bass=[0,6,16,25]),['roska','tech_house'],
        'Original broken-beat study: the first-bar closing snare is displaced by half a beat. Not a universal broken-beat grid.')
    add('broken_shuffle','Broken beat / shuffled rim circuit','Broken beat',126,
        dict(kick=[0,6,11,16,19,26],snare=back,hat=h16,rim=[3,7,11,15,19,23,27,31],bass=[0,10,16,29]),
        ['roska','tech_house'],'Only selected upper-percussion off-sixteenths swing; bass and main drums keep their authored positions.',F(5,8))
    add('afro_bell','Afro house / bell and kick weave','Afro house',120,
        dict(kick=q,clap=[12,28],hat=off,rim=[0,3,6,10,12,16,19,22,26,28],
             tom=[(7,.62),(15,.48),(23,.65),(31,.55)],shaker=h16,bass=[0,7,16,23]),['afro_house'],
        'Four-floor foundation with an original interlocking bell/tom arrangement. Rim synthesises a bell-like timing cue only.')
    add('afro_cross','Afro house / three-over-four percussion','Afro house',122,
        dict(kick=q,hat=off,clap=[4,12,20,28],tom=[(F(i*16,3),.65) for i in range(6)],
             shaker=h16,rim=[7,15,23,31],bass=[0,10,16,26]),['afro_house','ameme'],
        'Three equal tom accents per four-beat bar are retained as exact fractions over the quarter-kick layer.')
    add('gqom_space','Gqom / broken-kick space study','Gqom',124,
        dict(kick=[0,3,8,14,16,19,24,29],tom=[6,11,22,27],clap=[12,28],hat=[2,6,10,14,18,22,26,30],bass=[0,8,19,29]),
        ['gqom'],'Original sparse broken-kick design informed by DJ Lag’s description; no named Gqom track is transcribed.')
    add('gqom_exchange','Gqom / staggered drum exchange','Gqom',126,
        dict(kick=[0,6,9,16,23,26],tom=[3,11,14,19,27,30],rim=[4,12,20,28],shaker=h8,bass=[0,9,16,26]),
        ['gqom'],'A second authored conversation between low drums. Synthetic toms are timing cues, not authentic sample reconstruction.')
    add('baile_toms','Baile funk / low-drum conversation','Brazilian funk',132,
        dict(kick=[0,6,8,16,22,24],tom=[3,7,11,14,19,23,27,30],snare=[(4,.7),(12,.78),(20,.72),(28,.82)],hat=h8),
        ['brazil'],'Original low-drum/syncopation study, not a definitive tamborzão transcription. Distinct from drift phonk.')
    add('baile_response','Baile funk / syncopated answer','Brazilian funk',140,
        dict(kick=[0,3,10,16,22,25],tom=[6,11,14,18,27,30],rim=[4,12,20,28],hat=h16,bass=[0,10,16,25]),
        ['brazil'],'Original programmed variation using contrasting low/percussive answers; not a recording or scene-complete model.')
    add('reggae_one_drop','Reggae / one-drop foundation','Reggae and dub',76,
        dict(kick=repeat([8],2,1),rim=repeat([8],2,.88),hat=h8,bass=[(0,.8),(6,.62),(14,.55),(16,.8),(23,.62),(30,.58)]),
        ['reggae','one_drop'],'Kick and cross-stick coincide on beat 3 with beat 1 left empty in those lanes; bass is an original accompaniment.')
    add('reggae_steppers','Dub / steppers foundation','Reggae and dub',80,
        dict(kick=q,rim=repeat([8],2,.86),hat=h8,open_hat=[14,30],bass=[0,6,16,23]),['reggae','reggae_grids'],
        'Quarter-note kick with beat-3 cross-stick; the same four-floor kick has a different surrounding rhythmic context.')
    add('reggae_rockers','Reggae / kick-on-one-and-three study','Reggae and dub',82,
        dict(kick=repeat([0,8],2,1),rim=repeat([8],2,.85),hat=h8,tom=[(15,.35),(31,.5)],bass=[0,7,16,22,30]),
        ['reggae','reggae_grids'],'Illustrative rockers-style kick on 1 and 3; variants exist. Not every rockers groove uses this exact grid.')
    add('son_clave_32','Latin club / 3-2 son clave','Latin clave hybrids',120,
        dict(kick=q,rim=[0,6,12,20,24],hat=off,shaker=h16,tom=[(14,.4),(30,.55)],bass=[6,14,22,30]),
        ['son_clave','son_grid'],'Two-bar 3-2 son clave: 1, & of 2, 4 | 2, 3. Club kick/shaker orchestration is original.')
    add('son_clave_23','Latin club / 2-3 son clave','Latin clave hybrids',120,
        dict(kick=q,rim=[4,8,16,22,28],hat=off,shaker=h16,tom=[(10,.45),(30,.5)],bass=[2,14,18,30]),
        ['son_clave','son_grid'],'Two-bar 2-3 son clave reverses the two sides. Not interchangeable against an unchanged melodic phrase.')
    add('psy_rolling','Psy / straight rolling bass gaps','Trance and hard dance',145,
        dict(kick=q,bass=repeat([(i,.67 if i%4==2 else .48) for i in range(16) if i%4],2),
             hat=repeat([0,4,8,12],2,.26),open_hat=off,clap=[12,28]),['psy_bass','kilbourne'],
        'Original kick-bass-bass-bass sixteenth arrangement: three straight subdivisions, not a triplet. Short synth cues stand in for bass articulation.')
    add('psy_offbeat','Trance / offbeat bass exchange','Trance and hard dance',140,
        dict(kick=q,bass=repeat([2,6,10,14],2,.88),hat=h16,open_hat=[6,14,22,30],clap=back),['trance'],
        'Quarter kicks alternate with offbeat eighth-note bass; supporting hats and claps are authored.')
    add('hard_reverse','Hard dance / delayed bass swell cues','Trance and hard dance',150,
        dict(kick=q,bass=repeat([2,3,6,7,10,11,14,15],2,.62),clap=back,hat=off,crash=[0]),['kilbourne'],
        'Late-beat bass onsets cue a swelling response. Audio is simple bass synthesis, not a complete reverse-bass sound-design recreation.')
    add('italo_machine','Italo / machine rim conversation','Disco and electro',118,
        dict(kick=q,clap=back,hat=h16,open_hat=off,rim=[1,3,6,11,15,18,23,27,31],bass=[0,2,8,10,16,18,24,26]),
        ['italo'],'Original machine-style arrangement: straight kick/backbeat beneath a busy rim part and subtly shuffled hats.',F(11,20))
    add('electro_robot','Electro / asymmetric machine break','Disco and electro',128,
        dict(kick=[0,6,10,16,19,26],snare=back,hat=h16,open_hat=[14,30],rim=[(3,.42),(11,.4),(23,.44),(31,.5)],bass=[0,7,16,27]),
        ['edm'],'Original broken electro study using a drum-machine backbeat and syncopated kick/bass; no sampled break.')
    add('acid_percussion','Acid house / syncopated machine accents','House and techno II',126,
        dict(kick=q,clap=back,hat=h16,open_hat=off,rim=[3,6,11,14,19,22,27,30],bass=[0,3,7,8,11,15,16,19,23,24,27,31]),
        ['tech_house','four_floor'],'Original house grid with an asymmetric bass rhythm. This is not a 303 timbre emulator; acid character cannot be encoded by rhythm alone.')
    add('techno_rumble','Techno / delayed low-end answer','House and techno II',140,
        dict(kick=q,clap=[12,28],hat=h16,open_hat=off,bass=repeat([(1,.42),(3,.30),(5,.42),(7,.30),(9,.42),(11,.30),(13,.42),(15,.30)],2)),
        ['kilbourne','four_floor'],'Explicit delayed low-end cues approximate a kick-tail conversation, not acoustic convolution or a canonical techno beat.')
    add('ukg_rim_shuffle','Garage / rim-led skipping pocket','UK garage II',133,
        dict(kick=[0,10,16,23,26],snare=back,hat=h8,rim=[1,3,7,9,11,15,17,21,25,27,31],open_hat=[6,14,22,30],bass=[0,7,16,27]),
        ['garage'],'An original rim-led two-step variant; selected upper-percussion subdivisions use 5:3 swing.',F(5,8))
    add('dnb_push','DnB / kick pickup and ghost reply','Jungle and DnB II',172,
        dict(kick=[0,10,15,16,22,26],snare=back+[(7,.3),(23,.25),(31,.32)],hat=h16,ride=[2,6,10,14,18,22,26,30],bass=[0,10,16,26]),
        ['drumeo','edm'],'Original rolling break with a late first-bar pickup and quieter internal snares; not another recorded break transcription.')
    add('jungle_switchback','Jungle / two-bar switchback','Jungle and DnB II',168,
        dict(kick=[0,2,10,16,18,27],snare=[4,(7,.35),12,20,(23,.4),26,30],ride=h8,pedal_hat=[8,24],crash=[16],bass=[0,10,18,27]),
        ['jungle'],'Original break rearrangement with changing second-bar snare placement. Amen 05 remains unchanged as a separate study.')
    add('amapiano_answer','Amapiano / log-like bass answer','Amapiano II',112,
        dict(kick=[0,8,16,24],hat=off,shaker=h16,clap=[12,28],rim=[3,7,19,23],bass=[0,3,6,10,15,16,19,23,27,30]),
        ['amapiano'],'An original low-end/percussion call-and-response. Synth bass marks log-drum events but is not an authentic log-drum instrument model.')
    add('dancehall_space','Dancehall / spacious offbeat replies','Dancehall and reggaeton',96,
        dict(kick=[0,8,16,24],rim=[3,6,11,14,19,22,27,30],hat=h8,bass=[0,6,14,16,23,30]),
        ['reggaeton'],'An original sparse dancehall-influenced arrangement with displaced rim replies; not a historical riddim transcription.')
    add('dembow_push','Reggaeton / dembow with pickup answer','Dancehall and reggaeton',98,
        dict(kick=q,snare=repeat([3,6,11,14],2,.85),hat=h8,shaker=repeat([1,5,9,13],2,.28),
             rim=[(15,.35),(29,.4),(31,.5)],bass=[0,6,16,22,30]),['reggaeton'],
        'Common dembow-style snare displacement under quarter kicks with an original second-bar pickup and bass phrase.')
    if len(out) != 32: raise ValueError(f'Expected 32 new studies, got {len(out)}')
    return out


def all_rhythms():
    old = json.loads((ROOT/'collections/club/rhythms.json').read_text(encoding='utf-8'))['rhythms']
    result = old + new_rhythms()
    if len({r['id'] for r in result}) != len(result): raise ValueError('Duplicate rhythm id')
    return result


def _kernel_fields(r):
    """Periodic offline kernels; cost scales with support, not the full loop/event product."""
    period = float(F(r['period_beats'])); n = int(F(r['period_beats'])*64)
    fields = {lane: [0.0]*n for lane in LANES}
    signed = {lane: [0.0]*n for lane in LANES}
    spring = [[0.0]*n for _ in range(3)]
    targets = [[0.0]*n for _ in range(3)]
    counts = {lane:0 for lane in LANES}
    # Every distinct onset gets a direction. Simultaneous instruments share phase,
    # but have different lane offsets. Phase closes by construction each full loop.
    onsets = sorted({F(e['beat']) for e in r['events']})
    rank = {t:i for i,t in enumerate(onsets)}
    for e in r['events']:
        lane=e['lane'];t=float(F(e['beat']));v=e['velocity'];sign=1 if counts[lane]%2==0 else -1
        counts[lane]+=1
        attack,release=(.18,.80) if lane=='bass' else (.11,.48) if lane in ('kick','tom','crash') else (.07,.16) if lane in ('hat','shaker','ride','pedal_hat') else (.10,.32)
        angle=2*math.pi*rank[F(e['beat'])]/len(onsets)+LANES.index(lane)*.43
        vector=(math.cos(angle),math.sin(angle),.60*math.sin(2*angle+.30))
        weight=.36 if lane in ('hat','shaker','ride','pedal_hat') else .72 if lane=='bass' else 1
        # Evaluate exact fractional source onset, then sample at integer pips.
        for pip in range(math.floor((t-attack)*64),math.ceil((t+release)*64)+1):
            d=pip/64-t
            if not -attack<=d<=release: continue
            env=.5+.5*math.cos(math.pi*d/(attack if d<0 else release))
            value=env*v; i=pip%n
            fields[lane][i]+=value;signed[lane][i]+=value*sign
            for axis in range(3): targets[axis][i]+=value*weight*vector[axis]
        # Causal finite-support resonator: onset at rest, C1 rest at end.
        duration=1.50 if lane=='bass' else .90
        for pip in range(math.ceil(t*64),math.ceil((t+duration)*64)+1):
            d=pip/64-t
            if not 0<=d<=duration:continue
            u=d/duration
            env=math.sin(4*math.pi*u)*math.exp(-4*u)*(1-u)*(1-u)*v*weight
            i=pip%n
            for axis in range(3):spring[axis][i]+=env*vector[(axis+1)%3]
    return fields,signed,spring,targets


def _new_tables(r):
    f,g,spring,targets=_kernel_fields(r);n=len(f['kick'])
    def sum_lanes(lanes,src=f):return [sum(src[l][i] for l in lanes) for i in range(n)]
    k=f['kick'];s=sum_lanes(('snare','clap'));h=sum_lanes(('hat','shaker','open_hat','ride','pedal_hat'))
    b=f['bass'];t=sum_lanes(('rim','tom'));c=f['crash']
    ks=g['kick'];ss=sum_lanes(('snare','clap'),g);hs=sum_lanes(('hat','shaker','open_hat','ride','pedal_hat'),g)
    bs=g['bass'];ts=sum_lanes(('rim','tom'),g)
    fallback=[]
    if not any(s):s=[.70*v for v in k];ss=[.70*v for v in ks];fallback.append('backbeat -> 0.70 kick')
    if not any(h):h=[.45*v for v in k];hs=[.45*v for v in ks];fallback.append('upper percussion -> 0.45 kick')
    if not any(b):b=[.60*v for v in k];bs=[.60*v for v in ks];fallback.append('bass -> 0.60 kick')
    weights=[.30+.52*k[i]+.38*s[i]+.10*h[i]+.09*t[i]+.14*b[i] for i in range(n)]
    total=sum(weights);angles=[];acc=0
    for w in weights:angles.append(2*math.pi*acc/total);acc+=w
    tables={m:[] for m in MAPPINGS[4:]}
    corners=((-1,-1),(1,-1),(1,1),(-1,1))
    for i,a in enumerate(angles):
        sn,co=math.sin(a),math.cos(a);tw=math.sin(2*a)
        ki,si,hi,bi,ti=k[i],s[i],h[i],b[i],t[i]
        zks,zss,zhs,zbs,zts=ks[i],ss[i],hs[i],bs[i],ts[i]
        echo=s[(i-24)%n];ang=.80*sn+.17*zss
        radius=.43+.10*ki+.06*ti
        pos=(a/(2*math.pi)*4)%4;edge=int(pos);u=pos-edge;u=u*u*(3-2*u)
        x0,y0=corners[edge];x1,y1=corners[(edge+1)%4]
        values={
            'surge':(.18*zss+.06*zhs,.20*si-.28*ki-.03*hi,.62*ki-.19*bi+.07*ti),
            'recoil':(.49*zss-.20*zks-.13*echo,.23*ki+.06*hi,.15*zts-.12*bi),
            'flutter':(.26*sn+.22*zhs+.07*zts,.24*ki-.13*si+.12*hi,.17*tw+.09*bi),
            'dive':(.29*zbs+.14*zks+.06*zhs,-.18*si+.10*ti,.60*bi-.23*ki+.11*co),
            'pendulum':((.57+.12*ki)*math.sin(ang),.54*(1-math.cos(ang))-.20+.08*hi,.18*zss+.11*bi),
            'figure8':((.55+.08*ki)*sn,(.38+.06*si)*tw,.16*zss-.08*bi+.05*ti),
            'box':(.46*(x0+(x1-x0)*u)+.06*zss,.40*(y0+(y1-y0)*u)-.08*ki,.17*bi+.08*zhs),
            'corkscrew':(radius*math.cos(2*a),radius*math.sin(2*a),.42*sn+.12*bi-.08*si),
            'spiral':((.42+.17*sn+.08*ki)*math.cos(2*a),(.42+.17*sn+.08*ki)*math.sin(2*a),.19*co+.15*zss),
            'slalom':(.58*sn+.08*zss,.26*math.sin(3*a)-.15*ki+.08*hi,.28*math.cos(2*a)+.11*zbs),
            'spring':(.70*spring[0][i],.66*spring[1][i],.62*spring[2][i]),
            'ricochet':(.46*targets[0][i]+.08*co,.46*targets[1][i]-.12*ki,.44*targets[2][i]+.08*bi),
        }
        for name,v in values.items():tables[name].append(v)
    # Uniform scaling preserves the path, unlike clipping axes independently.
    for name,rows in tables.items():
        peak=max(abs(v) for row in rows for v in row);gain=min(1.0,.92/max(peak,1e-12))
        tables[name]=[tuple(0.0 if abs(v*gain)<5e-13 else round(v*gain,12) for v in row) for row in rows]
    return tables,fallback


def motion_tables(r):
    """Offline bulk baker. Old four mappings are returned only for the 32 new rhythms."""
    tables,fallback=_new_tables(r)
    old_ids={p['id'] for p in json.loads((ROOT/'collections/club/rhythms.json').read_text())['rhythms']}
    if r['id'] not in old_ids:
        for mapping in MAPPINGS[:4]:tables[mapping]=legacy.bake_motion(r,mapping)[0]
    return tables,fallback
