"""Expansion 03 / Motion Atlas: 256 original musical movement presets (MIT).

All equations and event composition here are OFFLINE authoring operations.
The generated C++ tables are the sole movement playback implementation.
No external presets, recordings, choreography, or source libraries are copied.
Quarter-note beats; exact Fraction timestamps; indexed, cyclic randomness.
"""
from __future__ import annotations

from fractions import Fraction as F
from hashlib import sha256
import bisect
import math

COLLECTION_ID = 'atlas-03'
PATTERN_COUNT = 256
TAU = 2 * math.pi
SIN, COS = math.sin, math.cos


def frac(value):
    return str(F(value))


def smooth(t):
    return t*t*t*(t*(t*6-15)+10)


def score(name, title, family, description, period=8, *, axes=None,
          events=None, gestures=None, parameters=None):
    return dict(name=name, description=description, period_beats=frac(period),
        tracks=[dict(axis=a, curve=c) for a, c in (axes or {}).items()],
        events=events or [], gestures=gestures or {}, bounds='reject', loop_policy='closed',
        provenance=dict(collection_id=COLLECTION_ID, title=title, family=family,
            author='Kieran Simkin / DanceRudiments', license='MIT', source_kind='original',
            source_url='https://github.com/kieransimkin/DanceRudiments',
            beat_unit='quarter_note', parameters=parameters or {},
            transformation=description,
            event_markers=[dict(beat=e['beat'], lane=e['gesture']) for e in (events or [])]))


def function_score(name, title, family, description, fn, period=8, **parameters):
    """Sample an explicitly closed vector function; scale all axes together.

    Values describe position, never brightness or whole-frame flashing. Extra
    samples check the function before baking (a periodic lookup alone would hide
    an open source path). Uniform scale preserves relative XY/XYZ geometry.
    """
    n = int(F(period)*64)
    if F(period)*64 != n or n < 64:
        raise ValueError('Use an integral pip period of at least one beat')
    ends = (fn(0.0), fn(1.0))
    if max(abs(a-b) for a,b in zip(*ends)) > 1e-8:
        raise ValueError('Source function is not closed: '+name)
    raw = [tuple(fn(i/n)) for i in range(n)]
    if any(len(v)!=3 or not all(math.isfinite(x) for x in v) for v in raw):
        raise ValueError('Invalid source positions: '+name)
    peak = max(abs(x) for v in raw for x in v)
    if peak < 1e-8:
        raise ValueError('Stationary source: '+name)
    scale = .82/peak
    axes = {}
    for j,axis in enumerate('xyz'):
        values = [0.0 if abs(v[j]*scale)<.5e-12 else round(v[j]*scale,12) for v in raw]
        if any(values):
            axes[axis] = dict(type='samples', period_beats=frac(period), values=values,
                              interpolation='linear')
    parameters.update(uniform_authoring_scale=round(scale,12), source_endpoint_error=0.0)
    return score(name,title,family,description,period,axes=axes,parameters=parameters)


def key_curve(points):
    return dict(type='keyframes', points=[dict(beat=frac(t),value=v,
                interpolation='smootherstep') for t,v in points])


def vector_cycle(points, weights=None):
    """Closed waypoint travel with a zero-velocity, zero-acceleration turn."""
    weights = weights or [1]*len(points)
    if len(points)!=len(weights) or any(w<=0 for w in weights):
        raise ValueError('Invalid waypoint timings')
    total=sum(weights);edges=[0.0]
    for w in weights: edges.append(edges[-1]+w/total)
    edges[-1]=1.0
    def at(p):
        if p>=1: return tuple(points[0])
        i=min(bisect.bisect_right(edges,p)-1,len(points)-1)
        t=smooth((p-edges[i])/(edges[i+1]-edges[i]))
        return tuple(a+(b-a)*t for a,b in zip(points[i],points[(i+1)%len(points)]))
    return at


def wave_scores():
    # Each entry alters shape, not merely amplitude, phase, rate or random seed.
    functions = [
        ('pinched', 'Pinched sine', lambda a:SIN(a)**3),
        ('shouldered', 'Shouldered sine', lambda a:SIN(a)*(1+.62*COS(2*a))),
        ('folded', 'Folded sine', lambda a:SIN(2.2*SIN(a))),
        ('double_fold', 'Double-fold wave', lambda a:SIN(3.8*SIN(a))),
        ('rounded_square', 'Rounded square', lambda a:math.tanh(2*SIN(a))),
        ('soft_rectifier', 'Soft rectified swell', lambda a:math.sqrt(SIN(a)**2+.13)-.7),
        ('skew_warp', 'Phase-skew sweep', lambda a:SIN(a+.7*SIN(a))),
        ('scoop_warp', 'Scooped return', lambda a:SIN(a+.8*COS(a)+.21*SIN(2*a))),
        ('shelf_wave', 'Shelf and scoop', lambda a:math.tanh(2*SIN(a))+.23*SIN(3*a+.4)),
        ('notched', 'Notched crest', lambda a:SIN(a)-.36*SIN(3*a)+.12*COS(5*a)),
        ('bottle', 'Bottle-neck swell', lambda a:SIN(a)/(1+.9*COS(a)**2)),
        ('reed', 'Reed flutter', lambda a:SIN(a)*(.68+.32*COS(7*a))),
        ('unequal_peaks', 'Unequal double crest', lambda a:.67*SIN(a)+.4*SIN(2*a+.8)),
        ('ripple_return', 'Rippled recovery', lambda a:SIN(a)+.18*SIN(5*a)*(.5+.5*COS(a))),
        ('soft_teeth', 'Soft triple teeth', lambda a:math.tanh(1.8*(SIN(a)+.4*SIN(3*a)))),
        ('warped_fold', 'Warped wave fold', lambda a:SIN(2.6*SIN(a+.34*SIN(2*a))))]
    return [function_score('wave_'+n,t,'Waves III',
                t+'; a continuous shaped control wave, mapped to horizontal displacement.',
                lambda p,f=f:(f(TAU*p),0,0), 8, wave=n)
            for n,t,f in functions]


def envelope_scores():
    layouts = [
        ('lift_hold_drop','Lift, hold, settle',[(0,0),(1,-.8),(3,-.8),(4,.2),(5,0),(8,0)]),
        ('inhale_exhale','Long inhale, short exhale',[(0,0),(5,-.8),(6,.1),(7,0),(8,0)]),
        ('triple_swell','Three unequal swells',[(0,0),(1,-.8),(2,0),(3,-.5),(4,0),(6,-.3),(8,0)]),
        ('rising_echo','Rising echo ladder',[(0,0),(1,-.25),(2,0),(3,-.5),(4,0),(5,-.8),(6,0),(8,0)]),
        ('falling_echo','Falling echo ladder',[(0,0),(1,-.8),(2,0),(3,-.45),(4,0),(5,-.15),(8,0)]),
        ('anticipation','Backward anticipation',[(0,0),(1,.35),(2,0),(3,-.82),(4,-.82),(6,.12),(8,0)]),
        ('plateau_scoop','Plateau then scoop',[(0,0),(1,-.7),(4,-.7),(5,-.3),(6,.4),(8,0)]),
        ('hesitant','Hesitant reach',[(0,0),(1,-.3),(2,-.2),(3,-.5),(4,-.4),(5,-.8),(8,0)]),
        ('double_hold','Two-height hold',[(0,0),(1,-.4),(3,-.4),(4,-.8),(6,-.8),(8,0)]),
        ('swell_recoil','Deep swell and recoil',[(0,0),(3,-.8),(4,.5),(5,-.2),(6,.08),(8,0)]),
        ('late_release','Late release',[(0,0),(4,-.8),(6,-.8),(7,.25),(8,0)]),
        ('split_attack','Split attack',[(0,0),(F(1,2),-.6),(1,-.2),(2,-.8),(5,-.2),(8,0)]),
        ('suspended','Suspended answer',[(0,0),(1,-.75),(2,0),(4,0),(6,-.55),(7,-.55),(8,0)]),
        ('valley_peaks','Valley between peaks',[(0,0),(1,-.7),(3,-.3),(4,-.82),(6,.2),(8,0)]),
        ('four_breaths','Four breathing accents',[(0,0),(1,-.7),(2,0),(3,-.5),(4,0),(5,-.8),(6,0),(7,-.3),(8,0)]),
        ('return_stair','Stepped soft recovery',[(0,0),(2,-.8),(3,-.8),(4,-.5),(5,-.5),(6,-.2),(7,-.2),(8,0)])]
    return [score('env_'+n,t,'Envelopes',t+' over an eight-beat phrase; smooth, resting joins.',
                   axes={'y':key_curve(points)}) for n,t,points in layouts]


def stepper_scores():
    patterns = [
        ('up_down',[-.8,-.3,.2,.8,.4,-.1]),
        ('pendulum',[0,.8,0,-.8,0,.4,0,-.4]),
        ('octave',[0,.8,.2,.65,-.2,-.8,-.4,-.65]),
        ('unequal',[0,.6,-.2,.8,-.7,.1]),
        ('question',[-.6,-.2,.3,.8,.6,.2]),
        ('answer',[.6,.1,-.8,-.5,-.1,.3]),
        ('ratchet',[0,.3,0,.6,0,.8,0,-.3]),
        ('stairs',[-.8,-.4,0,.4,.8,.8,0,-.8])]
    out=[]
    for n,values in patterns:
        for timing in ('even','lilt'):
            points=[(x,.28*SIN(i*TAU/len(values)),0) for i,x in enumerate(values)]
            weights=[1]*len(points) if timing=='even' else [2 if i%2==0 else 1 for i in range(len(points))]
            out.append(function_score('seq_'+n+'_'+timing,n.replace('_',' ').title()+' / '+timing,
                'Step sequences','A programmed position sequence with '+timing+' segment durations and softened transitions.',
                vector_cycle(points,weights),8, levels=values, segment_weights=weights))
    return out


def random_value(seed,index):
    raw=sha256(('DanceRudiments-atlas03:'+str(seed)+':'+str(index)).encode()).digest()
    return int.from_bytes(raw[:8],'big')/((1<<64)-1)*2-1


def noise_scores():
    out=[]
    # Presets differ by topology, knot count and periodic shaping, not just seed.
    for i,(count,mode) in enumerate([(5,'drift'),(7,'drift'),(9,'drift'),(11,'drift'),
            (6,'orbit'),(8,'orbit'),(10,'orbit'),(12,'orbit'),
            (5,'ripple'),(7,'ripple'),(9,'ripple'),(11,'ripple'),
            (6,'depth'),(8,'depth'),(10,'depth'),(12,'depth')]):
        points=[(random_value(731,i*37+k),random_value(991,i*41+k),random_value(211,i*43+k))
                for k in range(count)]
        base=vector_cycle(points)
        def fn(p,base=base,mode=mode):
            x,y,z=base(p);a=TAU*p
            if mode=='orbit':return ((.6+.2*x)*COS(a),(.6+.2*y)*SIN(a),0)
            if mode=='ripple':return (x+.15*SIN(5*a),y+.12*COS(3*a),0)
            if mode=='depth':return (x,y,.6*z)
            return (x,y,0)
        out.append(function_score('noise_'+mode+'_'+str(count),mode.title()+' / '+str(count)+' knots',
            'Looped noise','Indexed SHA-256 control points in a closed '+mode+' path. No mutable random state.',
            fn,16,knot_count=count,construction=mode,seed_family=[731,991,211]))
    return out


def harmonic_scores():
    out=[]
    specs=[(2,.18,0),(3,.22,0),(4,.25,0),(5,.28,0),(6,.25,0),(7,.2,0),(8,.15,0),(9,.13,0),
           (2,.34,.5),(3,.31,.8),(4,.29,1.1),(5,.26,1.4),(6,.23,1.7),(7,.2,2),(8,.17,2.3),(9,.14,2.6)]
    for i,(n,d,offset) in enumerate(specs):
        def fn(p,n=n,d=d,offset=offset):
            a=TAU*p;return (COS(a)+d*COS(n*a+offset),.72*SIN(a)-d*SIN((n+1)*a-offset),0)
        out.append(function_score('orbit_harmonic_'+str(i+1).zfill(2),
            'Harmonic orbit '+str(n)+' / '+('open' if offset==0 else 'offset'),
            'Harmonic orbits','An ellipse combined with unequal horizontal and vertical harmonic ripples.',
            fn,8,harmonic=n,depth=d,phase_offset=offset))
    return out


def lissajous_scores():
    pairs=[(1,3),(1,4),(1,5),(2,5),(2,7),(3,4),(3,5),(3,7),
           (3,8),(4,5),(4,7),(4,9),(5,6),(5,7),(5,8),(5,9)]
    return [function_score('weave_'+str(a)+'_'+str(b),str(a)+' by '+str(b)+' weave',
             'Lissajous II',f'{a} horizontal and {b} vertical cycles; a phase-offset, closed 16-beat traversal.',
             lambda p,a=a,b=b:(.8*SIN(a*TAU*p+.37),.65*SIN(b*TAU*p),0),16,
             horizontal_cycles=a,vertical_cycles=b,horizontal_phase_radians=.37) for a,b in pairs]


def polar_scores():
    out=[]
    for petals in (3,6,7,8,9,10,11,12):
        k=petals if petals%2 else petals//2
        span=math.pi if petals%2 else TAU
        def fn(p,k=k,span=span):
            a=span*p;r=COS(k*a);return (r*COS(a),r*SIN(a),0)
        out.append(function_score('polar_rose_'+str(petals),str(petals)+'-petal rose',
            'Polar paths','A complete signed-radius rose traversal; odd-petal roses use a half-turn parameter.',
            fn,16,petals=petals,parameter_span=span))
    for lobes in range(2,10):
        def fn(p,n=lobes):
            a=TAU*p;r=.58+.24*COS(n*a+.2*SIN(a));return (r*COS(a),r*SIN(a),0)
        out.append(function_score('polar_scallop_'+str(lobes),str(lobes)+'-scallop orbit',
            'Polar paths','A positive-radius scalloped loop; no centre crossings, with an asymmetrically bent lobe.',
            fn,16,lobes=lobes))
    return out


def spiro_scores():
    specs=[(3,1,.45),(4,1,.6),(5,2,.75),(5,1,.55),(7,2,.65),(7,3,.7),(8,3,.6),(9,4,.8)]
    out=[]
    for kind in ('inside','outside'):
        for R,r,d in specs:
            gcd=math.gcd(R,r);turns=r//gcd
            def fn(p,R=R,r=r,d=d,kind=kind,turns=turns):
                a=TAU*turns*p
                if kind=='inside':
                    k=R-r;return (k*COS(a)+d*r*COS(k/r*a),k*SIN(a)-d*r*SIN(k/r*a),0)
                k=R+r;return (k*COS(a)-d*r*COS(k/r*a),k*SIN(a)-d*r*SIN(k/r*a),0)
            out.append(function_score('spiro_'+kind+'_'+str(R)+'_'+str(r),
                kind.title()+' roll '+str(R)+':'+str(r),'Spirographs',
                'A closed '+kind+'-rolling circle trace, with pen radius smaller than the rolling radius.',
                fn,16,fixed_radius=R,rolling_radius=r,pen_ratio=d,parameter_turns=turns))
    return out


def spatial_scores():
    out=[]
    for a,b in [(2,5),(2,7),(3,4),(3,5),(3,7),(4,5),(4,7),(5,6)]:
        def fn(p,a=a,b=b):
            t=TAU*p;r=.58+.2*COS(b*t);return (r*COS(a*t),r*SIN(a*t),.42*SIN(b*t))
        out.append(function_score('space_torus_'+str(a)+'_'+str(b),f'Torus knot {a}:{b}',
            'Spatial loops','A genuine XYZ closed torus-knot trajectory. The demo uses an oblique projection.',
            fn,16,major_turns=a,tube_turns=b))
    for a,b,c in [(1,2,3),(1,3,4),(2,3,4),(2,3,7),(2,5,7),(3,4,5),(3,5,7),(4,5,7)]:
        out.append(function_score(f'space_weave_{a}_{b}_{c}',f'Spatial weave {a}:{b}:{c}',
            'Spatial loops','Three coprime-frequency coordinate lanes with distinct phase offsets.',
            lambda p,a=a,b=b,c=c:(SIN(a*TAU*p),.8*SIN(b*TAU*p+.4),.7*COS(c*TAU*p+.7)),
            16,cycles=[a,b,c]))
    return out


def mechanical_scores():
    functions=[
        ('piston_short','Short-rod piston',lambda a:(COS(a)+math.sqrt(4-SIN(a)**2)-2,.3*SIN(a),0)),
        ('piston_long','Long-rod piston',lambda a:(COS(a)+math.sqrt(16-SIN(a)**2)-4,.25*SIN(2*a),0)),
        ('offset_crank','Offset crank',lambda a:(COS(a)+math.sqrt(9-(SIN(a)+.6)**2)-2.8,.35*SIN(a),0)),
        ('scotch_yoke','Yoke with rocking linkage',lambda a:(COS(a),.35*SIN(a)+.18*SIN(3*a),0)),
        ('whitworth','Quick-return linkage study',lambda a:(SIN(a+.72*SIN(a)),.4*COS(a),0)),
        ('elliptic_cam','Elliptic cam follower',lambda a:(.3*SIN(a),1/math.sqrt(1+3*SIN(a)**2)-.65,0)),
        ('two_lobe_cam','Two-lobe cam follower',lambda a:(.3*SIN(a),.55*COS(2*a)+.2*COS(a),0)),
        ('three_lobe_cam','Three-lobe cam follower',lambda a:(.25*SIN(a),COS(3*a)+.2*COS(a),0)),
        ('escapement','Soft escapement study',lambda a:(math.tanh(3*SIN(a)),.35*COS(2*a)+.1*SIN(a),0)),
        ('paddle','Paddle-wheel tip',lambda a:(COS(a)+.23*COS(4*a),SIN(a)+.23*SIN(4*a),0)),
        ('wobble_plate','Wobble-plate trace',lambda a:(COS(a),.35*SIN(a),.5*SIN(2*a+.3))),
        ('rocking_beam','Rocking beam',lambda a:(SIN(.9*SIN(a)),1-COS(.9*SIN(a))+.1*SIN(2*a),0)),
        ('coupled_cranks','Coupled cranks',lambda a:(COS(a)+.35*COS(3*a+.6),SIN(a)-.35*SIN(3*a+.6),0)),
        ('crank_rocker','Crank and rocker study',lambda a:(COS(a),.6*math.atan(2*SIN(a)),.15*COS(3*a))),
        ('piston_balance','Piston and balance mass',lambda a:(COS(a),.5*SIN(2*a),.25*SIN(a))),
        ('cam_return','Cam rise and return',lambda a:(SIN(a+.8*SIN(a)),.4*COS(2*a+.3*SIN(a)),0))]
    return [function_score('mech_'+n,t,'Mechanisms',t+
        '; an original kinematic-style position study, not an engineering simulation.',
        lambda p,f=f:f(TAU*p),8,construction=n) for n,t,f in functions]


def gesture(axes,duration=F(3,5),peak=F(1,2)):
    return dict(axes=dict(zip('xyz',axes)),duration_beats=frac(duration),
                peak_fraction=frac(peak),shape='cosine')


def event(t,lane,strength=1,duration=None):
    e=dict(beat=frac(t),gesture=lane,anchor='peak',strength=strength)
    if duration is not None:e['duration_beats']=frac(duration)
    return e


def event_score(name,title,family,description,period,events,gestures,**params):
    return score(name,title,family,description,period,events=events,gestures=gestures,parameters=params)


def euclidean_scores():
    specs=[(2,5),(3,7),(3,10),(4,9),(4,11),(5,9),(5,11),(5,13),
           (5,14),(6,13),(7,12),(7,15),(7,17),(8,19),(9,20),(11,24)]
    out=[]
    for k,n in specs:
        hits=[i for i in range(n) if (i*k)%n<k]
        ev=[event(F(i,2),'r' if j%2==0 else 'l',.75 if j else 1) for j,i in enumerate(hits)]
        gs={'r':gesture((.75,-.32,0),F(3,4)),'l':gesture((-.75,-.32,0),F(3,4))}
        out.append(event_score(f'euclid_{k}_{n}',f'{k} accents in {n} eighths','Euclidean II',
            'Evenly distributed accents with alternating sides; first onset is the phrase accent.',
            F(n,2),ev,gs,pulses=k,steps=n,grid_beats='1/2',onset_steps=hits))
    return out


def interlock_scores():
    specs=[(2,5),(2,7),(2,9),(3,5),(3,7),(3,8),(3,10),(4,5),
           (4,7),(4,9),(5,6),(5,7),(5,8),(5,9),(6,7),(7,8)]
    out=[]
    for a,b in specs:
        gs={'left':gesture((-.62,-.26,0),F(7,10)),
            'right':gesture((.62,-.26,.22),F(7,10))}
        ev=[event(F(i*8,a),'left',.65 if i else 1) for i in range(a)]
        ev += [event(F(i*8,b),'right',.65 if i else 1) for i in range(b)]
        out.append(event_score(f'poly_{a}_{b}',f'{a} against {b} / spatial accents','Polyrhythms II',
            'Two independent pulse trains share an eight-beat boundary. Each right-lane gesture includes depth.',
            8,ev,gs,pulses=[a,b],alignment='shared phrase start'))
    return out


def additive_scores():
    groups=[(2,3),(3,2),(3,2,2),(2,3,2),(3,4),(4,3),(2,2,2,3),(2,3,2,2),
            (3,2,3,2),(3,3,2,3),(2,2,3,2,3),(3,3,3,2),(4,3,3),(3,4,4),
            (2,3,3,2,3),(3,3,3,4)]
    out=[]
    for group in groups:
        ev=[];cursor=F(0)
        for j,n in enumerate(group):
            ev.append(event(cursor,'r' if j%2==0 else 'l',1))
            for k in range(1,n):ev.append(event(cursor+F(k,2),'tap',.42))
            cursor+=F(n,2)
        gs={'r':gesture((.72,-.33,0),F(3,5)),'l':gesture((-.72,-.33,0),F(3,5)),
            'tap':gesture((0,-.27,.12),F(1,3))}
        key='_'.join(map(str,group))
        out.append(event_score('meter_'+key,' + '.join(map(str,group))+' eighths','Additive meters',
            'Group starts lean alternately left and right; quieter subdivisions mark the eighth-note grid.',
            cursor,ev,gs,eighth_note_groups=list(group),meter_numerator=sum(group),meter_denominator=8))
    return out


def swing_scores():
    out=[]
    for swing in (F(3,5),F(2,3),F(5,7),F(3,4)):
        for mode in ('push','answer','skip','shuffle'):
            ev=[]
            for b in range(8):
                if mode!='skip' or b%4!=2:ev.append(event(F(b),'r' if b%2==0 else 'l',.9 if b%4==0 else .65))
                if mode!='answer' or b>=4:
                    t=F(b)+swing
                    ev.append(event(t,'tap' if mode in ('push','skip') else ('l' if b%2==0 else 'r'),.5))
                if mode=='shuffle' and b%4==3:ev.append(event(F(b)+swing/2,'tap',.35,F(1,5)))
            gs={'r':gesture((.65,-.24,0),F(2,5)),'l':gesture((-.65,-.24,0),F(2,5)),
                'tap':gesture((.15,-.3,.18),F(1,4))}
            out.append(event_score('swing_'+mode+'_'+str(swing.numerator)+'_'+str(swing.denominator),
                mode.title()+' swing '+str(swing),'Swing studies',
                'Eight-beat '+mode+' score with offbeats at '+str(swing)+' of each beat; peaks follow the score.',
                8,ev,gs,offbeat_fraction=str(swing),form=mode))
    return out


def stick_scores():
    # Original sticking studies, NOT labelled as official PAS rudiments.
    strings=['RLRRLRLL','RRLRLLRL','RLLRLRRL','RRLLRLRL','RLRLRRLL','RRRLLLRL',
             'RLLLRRR L','RRLRRLLL','RLRRLLRL','RRLLRLLR','RLRLLRRL','RRRLRLLL',
             'RRRRLRLL','RRLLLRRL','RLRRRLLL','RRLRLLLR']
    out=[]
    for i,s in enumerate(strings):
        s=s.replace(' ','');ev=[]
        # Mirror the second half so hand identity also closes after the phrase.
        whole=s+''.join('L' if h=='R' else 'R' for h in s)
        for j,h in enumerate(whole):
            ev.append(event(F(j,2),'r' if h=='R' else 'l',1 if j%4==0 else .55,F(3,8)))
        gs={'r':gesture((.74,-.34,0),F(3,8)),'l':gesture((-.74,-.34,0),F(3,8))}
        out.append(event_score('stick_study_'+str(i+1).zfill(2),s+' / mirrored answer','Stick studies',
            'Original R/L movement study with accented group leads, followed by its hand-swapped answer. Not an official rudiment transcription.',
            8,ev,gs,sticking=whole,subdivision_beats='1/2',official_rudiment=False))
    return out


def gesture_path_scores():
    specs=[
        ('side_reach','Side reach',[(0,0,0),(.8,0,0),(.8,-.6,0),(0,0,0),(-.6,0,0)]),
        ('cross_reach','Cross and reach',[(-.7,.2,0),(.6,-.5,0),(-.6,-.5,0),(.7,.2,0)]),
        ('low_scoop','Low scoop',[(-.7,-.2,0),(-.4,.6,0),(.4,.6,0),(.7,-.2,0),(0,-.5,0)]),
        ('high_arc','High arc',[(-.8,0,0),(-.4,-.6,0),(.4,-.6,0),(.8,0,0),(0,.2,0)]),
        ('corner_taps','Corner taps',[(0,0,0),(-.7,-.5,0),(0,0,0),(.7,-.5,0),(0,0,0),(.7,.5,0),(0,0,0),(-.7,.5,0)]),
        ('diagonal_touch','Diagonal touch',[(-.7,.5,0),(0,0,0),(.7,-.5,0),(0,0,0),(.5,.3,0)]),
        ('box_return','Box and centre',[(-.6,.5,0),(-.6,-.5,0),(.6,-.5,0),(.6,.5,0),(0,0,0)]),
        ('zigzag_lift','Zigzag lift',[(-.7,.5,0),(.4,.1,0),(-.4,-.2,0),(.7,-.6,0),(0,0,0)]),
        ('duck_sway','Duck and sway',[(-.7,0,0),(-.35,.45,0),(0,.55,0),(.7,0,0),(.35,-.25,0),(0,-.3,0)]),
        ('push_pull','Push and pull',[(0,0,0),(.3,-.2,.8),(-.3,.2,-.6),(.5,.1,0)]),
        ('reach_depth','Reach through depth',[(-.5,.3,0),(0,-.6,.7),(.5,.3,0),(0,-.3,-.5)]),
        ('bow_turn','Bow and turn',[(-.6,0,0),(0,.6,.35),(.6,0,0),(0,-.25,-.45)]),
        ('heel_toe','Heel-toe abstract',[(0,0,0),(-.4,.3,0),(-.65,-.3,0),(0,0,0),(.4,.3,0),(.65,-.3,0)]),
        ('hop_answer','Hop and answer',[(0,0,0),(-.6,-.7,0),(-.6,0,0),(0,0,0),(.6,-.4,0),(.6,0,0)]),
        ('spiral_reach','Spiral reach',[(0,0,0),(.3,-.3,.2),(.6,0,.4),(.3,.6,.6),(-.6,.3,.2),(-.3,-.5,0)]),
        ('diamond_depth','Depth diamond',[(0,-.6,0),(.6,0,.6),(0,.6,0),(-.6,0,-.6)])]
    out=[]
    for i,(n,t,points) in enumerate(specs):
        weights=[2 if j==0 else 1+(j%3==2) for j in range(len(points))]
        out.append(function_score('gesture_'+n,t,'Gesture paths',
            'An original single-point '+t.lower()+' gesture. Abstract motion, not a full-body dance or biomechanical recording.',
            vector_cycle(points,weights),8,waypoints=[list(v) for v in points],segment_weights=weights))
    return out


def document():
    factories=[wave_scores,envelope_scores,stepper_scores,noise_scores,harmonic_scores,
        lissajous_scores,polar_scores,spiro_scores,spatial_scores,mechanical_scores,
        euclidean_scores,interlock_scores,additive_scores,swing_scores,stick_scores,gesture_path_scores]
    patterns=[]
    for factory in factories:
        group=factory()
        if len(group)!=16:raise ValueError(factory.__name__+' must provide 16 presets')
        patterns.extend(group)
    if len(patterns)!=PATTERN_COUNT or len({p['name'] for p in patterns})!=PATTERN_COUNT:
        raise ValueError('Atlas count or identifier collision')
    return dict(format='dancerudiments.score-pack',schema_version=1,patterns=patterns)
