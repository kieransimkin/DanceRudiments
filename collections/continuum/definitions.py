"""Continuum 04: 320 original cyclic path and phrase studies. MIT.

This module is an offline authoring recipe, not a playback implementation.
Generated C++ tables provide all runtime positions. No source presets, recordings
or choreography are imported. Descriptive mechanism/gesture names are analogies,
not claims of physical simulation or anatomically complete movement.
"""
from __future__ import annotations

import bisect
import json
from fractions import Fraction as F
import math

COLLECTION_ID = 'continuum-04'
PATTERN_COUNT = 320
TAU = math.tau
S, C = math.sin, math.cos


def ease(t):
    return t*t*t*(10+t*(-15+6*t))


def record(name, title, family, description, period, *, axes=None, events=None, parameters=None):
    return dict(name=name, description=description, period_beats=str(F(period)),
        tracks=[dict(axis=k, curve=v) for k,v in (axes or {}).items()],
        gestures=GESTURES if events else {}, events=events or [], bounds='reject', loop_policy='closed',
        provenance=dict(collection_id=COLLECTION_ID, title=title, family=family,
            author='Kieran Simkin / DanceRudiments', license='MIT', source_kind='original',
            source_url='https://github.com/kieransimkin/DanceRudiments',
            beat_unit='quarter_note', parameters=json.loads(json.dumps(parameters or {}, allow_nan=False)), transformation=description,
            event_markers=[dict(beat=e['beat'], lane=e['gesture']) for e in (events or [])]))


def path_score(name, title, family, description, fn, period=8, **parameters):
    """Validate the source function, then bake a closed, uniformly scaled path.

    A repeated array could conceal an open source. Check source endpoints and
    all oversampled positions first. Axis ratios are preserved by uniform scaling;
    no clipping or independent per-axis stretching is used.
    """
    pips=F(period)*64
    if pips.denominator!=1 or not 64<=pips<=65535:
        raise ValueError('Invalid integral pip period: '+name)
    n=int(pips)
    def checked(p):
        row=tuple(fn(p))
        if len(row)!=3 or any(not math.isfinite(v) for v in row):
            raise ValueError('Invalid source position: '+name)
        return row
    first,last=checked(0),checked(1)
    error=max(abs(a-b) for a,b in zip(first,last))
    if error>1e-8:raise ValueError('Open source path: '+name)
    dense=[checked(i/(2*n)) for i in range(2*n)]
    peak=max(abs(v) for row in dense for v in row)
    if peak<1e-8:raise ValueError('Stationary source: '+name)
    scale=.82/peak
    values=[tuple(0.0 if abs(v*scale)<.5e-12 else round(v*scale,12) for v in row)
            for row in dense[::2]]
    if max(math.dist(values[i],values[(i+1)%n]) for i in range(n))>.22:
        raise ValueError('Source moves too far per pip: '+name)
    axes={axis:dict(type='samples',period_beats=str(F(period)),interpolation='linear',
          values=[row[j] for row in values]) for j,axis in enumerate('xyz') if any(row[j] for row in values)}
    parameters.update(uniform_authoring_scale=round(scale,12),source_closed=True,
                      source_checks_per_cycle=2*n+1)
    return record(name,title,family,description,period,axes=axes,parameters=parameters)


def circuit(points, weights=None, *, cubic=False, tension=.75):
    """Closed waypoint path: eased straight segments or periodic Hermite tangents."""
    weights=weights or [1]*len(points)
    if len(points)<3 or len(points)!=len(weights) or any(w<=0 for w in weights):
        raise ValueError('Invalid closed circuit')
    edges=[0.0]
    for w in weights:edges.append(edges[-1]+w/sum(weights))
    edges[-1]=1.0
    m=len(points)
    def at(p):
        if p>=1:return tuple(points[0])
        i=min(max(0,bisect.bisect_right(edges,p)-1),m-1)
        t=(p-edges[i])/(edges[i+1]-edges[i]);a,b=points[i],points[(i+1)%m]
        if not cubic:
            u=ease(t);return tuple(x+(y-x)*u for x,y in zip(a,b))
        # Tangents are derivatives with respect to musical phase, not segment index.
        # This keeps velocity continuous even with unequal segment durations.
        dt=edges[i+1]-edges[i]
        prev_dt=weights[(i-1)%m]/sum(weights);next_dt=weights[(i+1)%m]/sum(weights)
        t0=tuple(tension*(b[j]-points[(i-1)%m][j])/(dt+prev_dt) for j in range(3))
        t1=tuple(tension*(points[(i+2)%m][j]-a[j])/(dt+next_dt) for j in range(3))
        return tuple((2*t**3-3*t*t+1)*a[j]+(t**3-2*t*t+t)*dt*t0[j]
                     +(-2*t**3+3*t*t)*b[j]+(t**3-t*t)*dt*t1[j] for j in range(3))
    return at


# Hand-authored geometric controls; points are dimensionless and are not joint poses.
ROUTES = [
 ('kite',[(0,-1,0),(.7,-.25,0),(.35,.8,0),(-.85,.15,0)]),
 ('hourglass',[(-.8,-.7,0),(.9,.6,0),(-.8,.8,0),(.7,-.9,0)]),
 ('hook',[(0,0,0),(-.8,-.2,0),(-.7,-.9,0),(.6,-.7,0),(.9,.5,0),(.1,.8,0)]),
 ('crown',[(-.9,.5,0),(-.8,-.6,0),(-.3,-.05,0),(0,-.9,0),(.4,-.05,0),(.8,-.6,0),(.9,.5,0)]),
 ('bow',[(-.9,0,0),(-.1,-.7,0),(.8,-.4,0),(.15,0,0),(.9,.65,0),(-.3,.8,0)]),
 ('crooked_cross',[(0,-.9,0),(.2,-.25,0),(.9,-.1,0),(.25,.25,0),(.1,.8,0),(-.3,.3,0),(-.8,.1,0),(-.3,-.3,0)]),
 ('asymmetric_star',[(0,-1,0),(.25,-.3,0),(.95,-.25,0),(.4,.25,0),(.6,.9,0),(-.1,.45,0),(-.7,.65,0),(-.5,-.1,0),(-.8,-.7,0),(-.2,-.4,0)]),
 ('scoop',[(-.85,-.5,0),(-.7,.5,0),(0,.9,0),(.9,.2,0),(.6,-.7,0),(.1,-.25,0)]),
 ('rising_kite',[(0,-1,.2),(.7,-.25,-.6),(.35,.8,.7),(-.85,.15,-.25)]),
 ('twisted_bow',[(-.9,0,.1),(-.1,-.7,.8),(.8,-.4,-.2),(.15,0,-.6),(.9,.65,.5),(-.3,.8,-.35)]),
 ('cup',[(-.8,-.8,0),(-.65,.65,.4),(.2,.85,-.3),(.85,.15,.6),(.6,-.8,0),(.25,-.4,-.5)]),
 ('bridge',[(-.9,.2,-.2),(-.5,-.8,.5),(.5,-.6,-.3),(.9,.3,.4),(.2,.6,-.7),(-.3,.7,.1)]),
 ('double_bay',[(-.9,0,0),(-.4,-.8,.3),(0,-.2,-.2),(.6,-.7,.6),(.9,.3,.1),(.3,.8,-.5),(-.2,.3,.3),(-.6,.7,-.4)]),
 ('slanted_loop',[(-.9,-.6,-.4),(.1,-.85,.3),(.75,-.25,.7),(.85,.5,-.1),(-.1,.8,-.65),(-.65,.4,.2)]),
 ('fork',[(0,.8,.2),(-.2,0,-.4),(-.85,-.5,.4),(-.25,-.7,.7),(.1,-.2,-.5),(.8,-.8,.25),(.55,.4,-.2)]),
 ('folded_crown',[(-.9,.5,-.4),(-.8,-.6,.5),(-.3,-.05,-.7),(0,-.9,.2),(.4,-.05,.6),(.8,-.6,-.4),(.9,.5,.5)]),
]


def ribbon_scores():
    specs=[(1,2,.22,.3),(1,3,.28,.45),(1,4,.19,.6),(1,5,.24,.35),
           (2,3,.18,.4),(2,5,.25,.55),(3,4,.2,.35),(3,5,.22,.65),
           (1,2,.4,.9),(1,3,.38,.75),(1,4,.35,.9),(1,5,.31,.8),
           (2,3,.37,.85),(2,5,.34,.7),(3,4,.31,.8),(3,5,.3,.9)]
    out=[]
    for i,(a,b,w,tilt) in enumerate(specs):
        def fn(p,a=a,b=b,w=w,tilt=tilt):
            u=TAU*p;angle=a*u+.19*S(u);r=.65+w*C(b*u+.25*S(2*u))
            return (r*C(angle),.7*r*S(angle)+.2*S(2*u),tilt*w*S(b*u+u)*C(angle))
        out.append(path_score(f'ribbon_{a}_{b}_{"deep" if i>=8 else "slim"}',
            f'Ribbon {a}:{b} / '+('deep' if i>=8 else 'slim'),'Ribbon sweeps',
            'A curved elliptical spine with variable radial width and linked depth deflection.',fn,16,
            spine_turns=a,ripples=b,width=w,depth=tilt))
    return out


def superellipse_scores():
    specs=[(.65,1,.13),(.8,2,.18),(1.2,3,.14),(1.6,4,.12),
           (.55,2,.2),(.75,3,.22),(1.35,4,.2),(1.8,5,.15),
           (.6,3,.18),(.9,4,.21),(1.45,5,.16),(1.9,6,.12),
           (.7,4,.2),(1.1,5,.17),(1.55,6,.19),(2,7,.1)]
    out=[]
    for i,(power,ripple,amount) in enumerate(specs):
        def fn(p,power=power,k=ripple,d=amount,i=i):
            a=TAU*p
            x=math.copysign(abs(C(a))**power,C(a));y=math.copysign(abs(S(a))**power,S(a))
            r=1+d*S(k*a+.25*C(a))
            return (r*x+.12*S(2*a),.72*r*y,.2*S(3*a)*y if i>=8 else 0)
        out.append(path_score(f'contour_shaped_{i+1:02}',f'Shaped contour / {i+1:02}',
            'Rounded contours','Signed-power oval edges with local ripples and an asymmetric bow.',fn,16,
            signed_power=power,ripple=ripple,amount=amount,depth=i>=8))
    return out


def fourier_scores():
    specs=[(1,2,3,.2,.16),(1,3,5,.35,.12),(2,3,4,.3,.18),(2,5,7,.23,.16),
           (1,4,7,.35,.21),(3,4,5,.28,.14),(2,7,9,.19,.12),(3,5,8,.3,.17),
           (1,2,5,.4,.22),(1,5,8,.27,.24),(2,3,7,.34,.2),(3,7,10,.26,.16),
           (2,4,9,.33,.23),(3,4,9,.29,.25),(4,5,7,.25,.21),(4,7,11,.21,.16)]
    return [path_score(f'silhouette_harmonic_{i+1:02}',f'Harmonic silhouette / {a}-{b}-{c}',
        'Fourier silhouettes','Three unequal harmonic components, with cross-axis phases and a small linked depth term.',
        lambda p,a=a,b=b,c=c,d=d,e=e:(C(a*TAU*p)+d*S(b*TAU*p+.3)+e*C(c*TAU*p),
          .65*S(a*TAU*p+.2)-d*C(c*TAU*p+.1)+e*S(b*TAU*p),.12*S((a+b)*TAU*p)*S(TAU*p)),
        16,harmonics=[a,b,c],secondary_weights=[d,e]) for i,(a,b,c,d,e) in enumerate(specs)]


def spline_scores():
    return [path_score('spline_'+name,name.replace('_',' ').title()+' / spline',
        'Spline circuits','Periodic cubic tangents connect asymmetrical controls with unequal segment times.',
        circuit(points,[1+(j%3)*.35 for j in range(len(points))],cubic=True,tension=.9),8,
        points=points,tension=.9) for name,points in ROUTES]


def polygon_scores():
    out=[]
    specs=[(5,2),(7,2),(7,3),(8,3),(9,2),(9,4),(10,3),(11,2),
           (11,3),(11,4),(12,5),(13,2),(13,3),(13,4),(13,5),(14,3)]
    for i,(n,skip) in enumerate(specs):
        points=[]
        for j in range(n):
            a=TAU*((j*skip)%n)/n;r=.78+.16*C(3*a+.2)
            points.append((r*C(a),.68*r*S(a),.22*S(2*a) if i>=8 else 0))
        out.append(path_score(f'tour_{n}_{skip}',f'{n}-corner tour / stride {skip}',
            'Corner tours','A noncircular vertex tour with eased corners and alternating dwell lengths.',
            circuit(points,[1.5 if j%3==0 else 1 for j in range(n)]),16,
            corners=n,stride=skip,points=points))
    return out


def raster_scores():
    out=[]
    for rows in (3,4,5,6):
        for mode in ('flat','bowed','tilted','depth'):
            points=[]
            for j in range(rows):
                y=-.7+1.4*j/(rows-1);sign=1 if j%2==0 else -1
                for side in (-sign,sign):
                    x=.7*side;z=0
                    if mode=='bowed':x+=.2*C(math.pi*y);y1=y+.1*S(2*x)
                    else:y1=y
                    if mode=='tilted':x,y1=x+.3*y,y-.2*x
                    if mode=='depth':z=.38*S(j*math.pi/(rows-1)+.4*side)
                    points.append((x,y1,z))
            # Explicit outside return avoids an unmarked reset or teleport.
            points.extend([(.98,1.0,.1 if mode=='depth' else 0),(-1.0,1.0,0),(-1.0,-.95,0)])
            out.append(path_score(f'scan_{mode}_{rows}',f'{mode.title()} scan / {rows} rows',
                'Serpentine scans','An eased serpentine scan and an explicit outer return to the starting point.',
                circuit(points),16,rows=rows,construction=mode,points=points))
    return out


def petal_scores():
    out=[]
    for petals in (3,4,5,7):
        for mode in ('scoop','hook','lift','recoil'):
            def fn(p,k=petals,mode=mode):
                if p>=1:p=0
                q=p*k;i=int(q);t=q-i;a=TAU*i/k+.12*S(TAU*i/k)
                r=S(math.pi*t)**2*(1+.22*S(2*math.pi*t));side=.23*S(TAU*t)*S(math.pi*t)**2
                if mode=='hook':side+=.4*S(math.pi*t)**4
                if mode=='recoil':r*=1+.32*S(3*math.pi*t)
                z=.5*S(math.pi*t)**2*C(a) if mode=='lift' else 0
                return (r*C(a)-side*S(a),.8*r*S(a)+side*C(a),z)
            out.append(path_score(f'reach_{mode}_{petals}',f'{petals}-direction {mode}',
                'Petal journeys','Separate shaped reaches depart from and settle at a shared centre, without reset jumps.',
                fn,16,directions=petals,gesture=mode))
    return out


def spherical_scores():
    specs=[(1,2,.5),(1,3,.65),(1,4,.8),(1,5,.55),(2,3,.6),(2,5,.75),(3,4,.5),(3,5,.7),
           (1,2,1.1),(1,3,1.2),(1,4,1.0),(1,5,1.25),(2,3,1.15),(2,5,1.0),(3,4,1.2),(3,5,1.05)]
    out=[]
    for i,(turns,lobes,depth) in enumerate(specs):
        def fn(p,a=turns,b=lobes,d=depth):
            u=TAU*p;longitude=a*u+.22*S(2*u);latitude=d*S(b*u+.17*S(u));radius=.8+.12*C(3*u)
            return (radius*C(latitude)*C(longitude),radius*C(latitude)*S(longitude),radius*S(latitude))
        out.append(path_score(f'surface_{turns}_{lobes}_{"wide" if i>=8 else "low"}',
            f'Latitude {turns}:{lobes} / '+('wide' if i>=8 else 'low'),'Surface travels',
            'A varying-radius surface path with coupled longitude and latitude; all three coordinates are retained.',
            fn,16,longitude_turns=turns,latitude_waves=lobes,latitude_depth=depth))
    return out


def braid_scores():
    out=[]
    for i,(a,b) in enumerate([(1,2),(1,3),(1,4),(1,5),(2,3),(2,5),(3,4),(3,5),
                              (1,6),(2,7),(3,7),(4,5),(4,7),(5,6),(5,7),(5,8)]):
        def fn(p,a=a,b=b):
            u=TAU*p;v=a*u+.25*S(u);roll=b*u
            return ((.65+.18*C(roll))*C(v)+.12*S(2*u),
                    (.65+.18*C(roll))*S(v),.25*S(roll)+.18*S((a+b)*u+.2)*S(u))
        out.append(path_score(f'braid_{a}_{b}',f'Braided tube / {a}:{b}','Braided loops',
            'An offset tube centreline and a rolling cross-section with a second depth ripple.',fn,16,
            centreline_turns=a,cross_section_turns=b))
    return out


def linkage_scores():
    specs=[(1,2,.6,.4),(1,3,.75,.35),(2,3,.8,.45),(2,5,.6,.3),
           (1,4,.9,.5),(3,4,.7,.45),(3,5,.55,.5),(2,7,.65,.3),
           (1,2,1.2,.75),(1,3,1.3,.65),(2,3,1.15,.8),(2,5,1.4,.7),
           (1,4,1.2,.9),(3,4,1.35,.7),(3,5,1.15,.9),(2,7,1.25,.8)]
    out=[]
    for i,(a,b,angle,elbow) in enumerate(specs):
        def fn(p,a=a,b=b,k=angle,e=elbow,i=i):
            u=TAU*p;q=k*S(a*u)+.18*S(2*u);r=q+e*S(b*u+.4)
            return (S(q)+.48*S(r),-C(q)-.48*C(r),.32*S(u)*C(r) if i>=8 else 0)
        out.append(path_score(f'arm_coupled_{i+1:02}',f'Coupled arm / {a}:{b} / {i+1:02}',
            'Linkage portraits','Tip position of two kinematically driven links; not a dynamics simulation or anatomical model.',
            fn,16,drivers=[a,b],shoulder=angle,elbow=elbow))
    return out


def cam_scores():
    # Four-step lift/dwell/fall/rest units are composed into an unequal full phrase.
    out=[]
    specs=[(1,1,2,2),(2,1,1,2),(1,2,2,1),(2,2,1,1),(1,3,1,2),(3,1,2,1),(2,3,1,2),(3,2,2,1),
           (1,1,3,2),(2,1,3,1),(1,3,2,2),(3,1,1,3),(2,2,3,1),(3,3,1,2),(1,2,3,3),(2,3,3,2)]
    for i,w in enumerate(specs):
        points=[(-.65,.25,0),(-.3,-.65,.2),(-.3,-.65,.2),(.7,.1,-.15),(.7,.1,-.15),(.05,.6,.35),(-.65,.25,0)]
        weights=[w[0],w[1],w[2],w[3],1+(i%3),2,1]
        if i>=8:points[3]=(.75,-.3,-.45);points[4]=points[3];points[5]=(.15,.8,.5)
        out.append(path_score(f'dwell_phrase_{i+1:02}',f'Dwell and transfer / {i+1:02}','Dwell phrases',
            'Two unequal lift-and-hold gestures, a transfer and a settling return; holds have finite musical duration.',
            circuit(points,weights),16,weights=weights,points=points))
    return out


def packet_scores():
    out=[]
    for count in (2,3,4,5):
        for mode in ('alternating','cascading','crossing','depth'):
            def fn(p,k=count,mode=mode):
                x=y=z=0.
                for j in range(k):
                    centre=(j+.35+.08*S(j+1))/k;half=.42/k
                    # shortest cyclic phase distance, no history or mutable RNG
                    t=((p-centre+.5)%1-.5)/half
                    if abs(t)>=1:continue
                    e=(1-t*t)**3;carrier=C(math.pi*(j%3+1)*t)
                    weight=(.85**j if mode=='cascading' else 1)
                    x+=weight*e*carrier*(-1 if j%2 else 1)
                    y+=.55*e*S(math.pi*t)*(1 if mode=='crossing' else (-1)**j)
                    if mode=='depth':z+=.5*e*S(2*math.pi*t)
                return x,y,z
            out.append(path_score(f'packet_{mode}_{count}',f'{count}-packet {mode}',
                'Resonant packets','Compact, smooth-edged oscillation packets arranged around a closed phrase, with shaped side motion.',
                fn,8,packet_count=count,arrangement=mode))
    return out


GESTURES={
    'left':dict(duration_beats='3/8',axes=dict(x=-.31,y=-.12),shape='cosine',peak_fraction='2/5'),
    'right':dict(duration_beats='3/8',axes=dict(x=.29,y=-.15),shape='cosine',peak_fraction='3/5'),
    'up':dict(duration_beats='1/2',axes=dict(x=.06,y=-.32,z=.12),shape='smoothstep',peak_fraction='1/3'),
    'down':dict(duration_beats='1/2',axes=dict(x=-.04,y=.3,z=-.09),shape='cosine',peak_fraction='2/3'),
    'near':dict(duration_beats='3/8',axes=dict(x=.08,y=.05,z=.32),shape='smoothstep',peak_fraction='1/2'),
}


def event(t,lane,strength=1,duration=None,period=8):
    e=dict(beat=str(F(t)%F(period)),gesture=lane,anchor='peak',strength=round(strength,6))
    if duration is not None:e['duration_beats']=str(F(duration))
    return e


def rhythm(name,title,family,description,events,period=8,**parameters):
    # Stable ordering is essential for byte-reproducible overlapping-gesture sums.
    events=sorted(events,key=lambda e:(F(e['beat']),e['gesture'],e['strength']))
    return record(name,title,family,description,period,events=events,parameters=parameters)


MOTIFS=[(0,3,7,10),(0,2,5,11),(0,4,6,9),(0,1,7,9),(0,3,5,8,11),(0,2,7,10,11),(0,1,4,8,10),(0,2,3,6,9)]


def canon_scores():
    out=[]
    for i,motif in enumerate(MOTIFS):
        for delayed in (False,True):
            delay=F(5,6) if delayed else F(1,3);ev=[]
            for m in motif:
                t=F(m,3)
                ev.extend([event(t,'left',.9),event(t+delay,'right',.7),event(t+4,'near',.6),event(t+4+2*delay,'up',.55)])
            out.append(rhythm(f'canon_{i+1:02}_{"late" if delayed else "close"}',
                f'Canon {i+1:02} / '+('late' if delayed else 'close'),'Rhythmic canons',
                'A rational-beat motif passes between lateral and depth lanes, with an altered second-half response.',ev,
                motif_thirds=list(motif),delay_beats=str(delay)))
    return out


def echo_scores():
    out=[]
    for n in (3,4,5,6):
        for mode in ('regular','shrinking','expanding','crossed'):
            ev=[];times=[];t=F(0)
            for j in range(n):
                times.append(str(t));duration=F(1,4) if mode=='shrinking' else F(3,8)
                lane=('left','up','right','near')[j%4] if mode=='crossed' else ('left' if j%2==0 else 'right')
                ev.append(event(t,lane,.83**j,duration))
                ev.append(event(t+4,'down' if j%2==0 else 'near',.8*.86**j,duration))
                t+=F(1,2) if mode in ('regular','crossed') else (F(n-j,2*n) if mode=='shrinking' else F(j+1,2*n))
            out.append(rhythm(f'echo_{mode}_{n}',f'{n}-answer {mode} echo','Echo conversations',
                'An original decaying call and a differently directed answer; echo spacing is preserved as fractions.',ev,
                echo_times=times,spacing=mode,echo_count=n))
    return out


def ladder_scores():
    specs=[(2,3,4,6),(3,5,4,2),(2,5,3,7),(4,3,6,5),(2,4,7,3),(3,6,2,5),(5,3,7,4),(6,4,3,2),
           (2,7,4,5),(7,3,5,2),(4,7,3,6),(5,2,6,3),(3,4,5,7),(6,5,4,3),(7,5,3,4),(4,6,7,5)]
    out=[]
    for spec in specs:
        ev=[]
        for bar,n in enumerate(spec):
            for j in range(n):
                ev.append(event(2*bar+F(2*j,n),('left','right','near','up')[(j+bar)%4],
                                1 if j==0 else .6+.08*(j%3),min(F(3,8),F(3,2*n))))
        out.append(rhythm('ladder_'+'_'.join(map(str,spec)),'Subdivision ladder / '+':'.join(map(str,spec)),
            'Subdivision ladders','Four two-beat regions change subdivision density while accents mark region starts.',ev,
            pulses_per_region=list(spec),region_beats=2))
    return out


def necklace_scores():
    words=['1001011000101100','1010001101010010','1100100100011010','1011010001001001',
           '1000110101100010','1101000100101010','1010010011100010','1110001001010010',
           '1001100010100101','1100010100100110','1010100011001001','1001001111010010',
           '1100101000101001','1011000100010110','1001010010011100','1110010001010100']
    out=[]
    for i,word in enumerate(words):
        ev=[]
        for j,c in enumerate(word):
            lane='left' if c=='1' else 'right';strength=.8 if c=='1' else .35
            ev.append(event(F(j,2),lane,strength,F(1,3)))
            if c=='1' and word[(j-1)%16]=='0':ev.append(event(F(j,2)+F(1,6),'near',.5,F(1,4)))
        out.append(rhythm(f'necklace_{i+1:02}',f'Complementary necklace / {i+1:02}','Rhythm necklaces',
            'A hand-authored binary accent word; its complement moves the other side and rising accents add depth.',ev,
            accent_word=word))
    return out


def migration_scores():
    out=[]
    specs=[(5,1),(5,2),(7,1),(7,2),(7,3),(8,1),(8,3),(9,1),(9,2),(9,4),(10,3),(11,2),(11,3),(12,5),(13,3),(13,5)]
    for grid,stride in specs:
        ev=[]
        for bar in range(4):
            for j in range(grid):
                accented=(j-bar*stride)%grid in (0,2)
                ev.append(event(4*bar+F(4*j,grid),'left' if (j+bar)%2==0 else 'right',
                    .95 if accented else .4,min(F(3,8),F(3,grid)),16))
                if accented:ev.append(event(4*bar+F(4*j,grid),'near',.48,F(1,3),16))
        out.append(rhythm(f'accent_walk_{grid}_{stride}',f'Accent walk / {grid} steps / stride {stride}',
            'Travelling accents','A four-bar grid keeps its pulse spacing while a two-accent motif migrates between bars.',ev,16,
            pulses_per_bar=grid,accent_stride=stride,bars=4))
    return out


def triplet_scores():
    out=[]
    masks=['101110101001','110101011010','111010100110','101011110001',
           '110110010011','100111011100','111001010101','101101001110']
    for i,mask in enumerate(masks):
        for mode in ('answer','turnaround'):
            ev=[]
            for j in range(24):
                if mask[(j+(3 if mode=='turnaround' and j>=12 else 0))%len(mask)]=='1':
                    ev.append(event(F(j,3),('left','near','right')[j%3],.95 if j%6==0 else .65,F(1,4)))
                elif mode=='answer':ev.append(event(F(j,3)+F(1,6),'up',.6,F(1,4)))
            out.append(rhythm(f'triplet_{i+1:02}_{mode}',f'Broken triplets {i+1:02} / {mode}',
                'Broken triplets','Triplet-grid gestures with deliberate omissions; gaps either answer off-grid or rotate after four beats.',ev,
                twelve_step_mask=mask,response=mode))
    return out


def meter_scores():
    specs=[(3,4,5),(5,3,4),(3,5,2),(2,5,4),(4,3,2),(3,2,4,5),(5,2,3,4),(2,3,5,3),
           (3,4,3,5),(5,4,2,3),(2,4,5,2),(4,5,3,2),(3,5,4,3),(5,3,2,5),(2,5,3,5),(4,3,5,4)]
    out=[]
    for spec in specs:
        period=F(sum(spec),2);ev=[];start=F(0)
        for group,n in enumerate(spec):
            for j in range(n):
                ev.append(event(start+F(j,2),('left','right','up','near')[group%4],1 if j==0 else .55,F(3,8),period))
                if j==n-1:ev.append(event(start+F(j,2)+F(1,4),'down',.45,F(1,4),period))
            start+=F(n,2)
        out.append(rhythm('dialogue_'+'_'.join(map(str,spec)),'Meter dialogue / '+'+'.join(map(str,spec)),
            'Meter dialogues','Different eighth-note group lengths pass a phrase between directions, with late pickup responses.',ev,period,
            eighth_note_groups=list(spec)))
    return out


def burst_scores():
    specs=[(3,5,2),(4,3,6),(5,2,4),(2,7,3),(3,4,5),(5,3,7),(6,2,5),(4,7,2),
           (7,3,4),(2,5,6),(5,7,3),(3,6,4),(4,5,7),(6,3,5),(7,4,3),(5,6,2)]
    out=[]
    for a,b,c in specs:
        ev=[]
        for region,n in enumerate((a,b,c)):
            for j in range(n):
                t=F(5*region,2)+F(3*j,2*n)
                ev.append(event(t,('left','up','right')[region],.9-.25*j/max(1,n-1),F(1,5)))
                if j%2==0:ev.append(event(t+F(1,6),'near',.42,F(1,5)))
        ev.append(event(F(31,4),'down',.8,F(1,3)))
        out.append(rhythm(f'burst_{a}_{b}_{c}',f'Alternating bursts / {a}:{b}:{c}','Alternating bursts',
            'Three unevenly subdivided directional bursts, deliberate gaps and a late settling accent.',ev,
            burst_pulses=[a,b,c],region_starts=['0','5/2','5'] ))
    return out


def document():
    families=[ribbon_scores,superellipse_scores,fourier_scores,spline_scores,polygon_scores,raster_scores,
              petal_scores,spherical_scores,braid_scores,linkage_scores,cam_scores,packet_scores,
              canon_scores,echo_scores,ladder_scores,necklace_scores,migration_scores,triplet_scores,
              meter_scores,burst_scores]
    patterns=[]
    for factory in families:
        batch=factory()
        if len(batch)!=16:raise ValueError('Expected 16 presets from '+factory.__name__)
        patterns.extend(batch)
    if len(patterns)!=PATTERN_COUNT or len({p['name'] for p in patterns})!=PATTERN_COUNT:
        raise ValueError('Continuum count/name mismatch')
    return dict(format='dancerudiments.score-pack',schema_version=1,patterns=patterns)
