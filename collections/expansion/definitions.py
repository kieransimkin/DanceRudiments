"""Expansion 02: 24 original, closed, beat-indexed motion scores (MIT).

Authoring-time equations only. Playback uses generated C++ tables. Time is in
quarter-note beats; fractional events stay rational until the 64-pip sampling.
No external presets, recordings, datasets, or runtime dependencies are used.
"""
from __future__ import annotations

from fractions import Fraction
import math

COLLECTION_ID = 'expansion-02'
AUTHOR = 'Kieran Simkin / DanceRudiments'
PROJECT_URL = 'https://github.com/kieransimkin/DanceRudiments'
TAU = 2 * math.pi


def ratio(value):
    return str(Fraction(value))


def osc(period, gain=1, phase=0, offset=0):
    return dict(type='lfo', shape='sine', period_beats=ratio(period),
                phase=ratio(phase), gain=gain, offset=offset)


def keys(points):
    return dict(type='keyframes', points=[dict(beat=ratio(t), value=v,
                interpolation='smootherstep') for t, v in points])


def tabulated(function, period):
    # Pre-round authoring-time libm tails so the score's identity is reproducible.
    values = []
    for i in range(period * 64):
        v = function(i / (period * 64))
        values.append(0.0 if abs(v) < .5e-12 else round(v, 12))
    return dict(type='samples', values=values, period_beats=ratio(period),
                interpolation='linear')


def gesture(x=0, y=0, z=0, duration=Fraction(1, 2)):
    return dict(duration_beats=ratio(duration), axes=dict(x=x, y=y, z=z),
                peak_fraction='1/2', shape='cosine')


def event(beat, key, strength=1, duration=None):
    result = dict(beat=ratio(beat), gesture=key, strength=strength, anchor='peak')
    if duration is not None:
        result['duration_beats'] = ratio(duration)
    return result


def score(name, title, family, description, period=8, axes=None,
          events=None, gestures=None, **metadata):
    return dict(name=name, description=description, period_beats=ratio(period),
                tracks=[dict(axis=a, curve=c) for a, c in (axes or {}).items()],
                gestures=gestures or {}, events=events or [], bounds='reject',
                loop_policy='closed', provenance=dict(
                    collection_id=COLLECTION_ID, title=title, family=family,
                    author=AUTHOR, license='MIT', source_kind='original',
                    source_url=PROJECT_URL, transformation=description,
                    beat_unit='quarter_note', **metadata))


def lfo_scores():
    out = []
    out.append(score('lfo_twin_swell', 'Unequal twin swells', 'LFO II',
        'Two broad swells of unequal depth, with a gentle lateral answer. Eight beats.',
        axes={'y': keys([(0, 0), (2, -.85), (4, 0), (6, -.45), (8, 0)]),
              'x': keys([(0, 0), (2, .2), (4, 0), (6, -.32), (8, 0)])}))
    out.append(score('lfo_pulse_hold', 'Pulse, hold & recoil', 'LFO II',
        'A smooth outward pulse, sustained plateau, smaller opposite recoil, and rest.', 4,
        axes={'x': keys([(0, 0), (Fraction(1, 2), .8), (2, .8),
                         (Fraction(5, 2), -.35), (3, 0), (4, 0)])}))
    out.append(score('lfo_sweep_ratchet', 'Sweep into ratchets', 'LFO II',
        'A slow lateral sweep followed by three decaying vertical ratchets; no reset jump.',
        axes={'x': keys([(0, -.75), (4, .75), (6, .75), (8, -.75)])},
        events=[event(Fraction(4)+Fraction(i, 2), 'ratchet', 1-.22*i) for i in range(3)],
        gestures={'ratchet': gesture(y=-.65, duration=Fraction(3, 8))}))
    out.append(score('lfo_triplet_wobble', 'Breathing triplet wobble', 'LFO II',
        'Three rounded oscillations per two beats, breathing in depth over an eight-beat phrase.',
        axes={'x': dict(type='product', curves=[osc(Fraction(2, 3), .85),
                       osc(8, .3, Fraction(-1, 4), .65)]),
              'y': osc(8, .22)}, subdivision_beats='2/3'))
    out.append(score('lfo_breathing_orbit', 'Breathing orbit', 'LFO II',
        'A closed ellipse expands and contracts twice during its eight-beat revolution.',
        axes={'x': tabulated(lambda p: (.56+.22*math.cos(2*TAU*p))*math.cos(TAU*p), 8),
              'y': tabulated(lambda p: (.48+.18*math.cos(2*TAU*p))*math.sin(TAU*p), 8)}))
    out.append(score('lfo_seeded_drift', 'Seeded wandering loop', 'LFO II',
        'Two independently seeded smooth random lanes; irregular-looking but exactly periodic and seekable.', 16,
        axes={'x': dict(type='random_smooth', steps=8, seed=29092026, period_beats='16', gain=.8),
              'y': dict(type='random_smooth', steps=5, seed=6402, period_beats='16', gain=.65)},
        random_note='Indexed SHA-256 values, cyclic smoothstep; no stateful random walk.'))
    out.append(score('lfo_pendulum_dwell', 'Pendulum with dwell', 'LFO II',
        'Rounded saturation slows the pendulum near either side; a shallow arc connects the turns.',
        axes={'x': tabulated(lambda p: .78*math.tanh(2.8*math.sin(TAU*p))/math.tanh(2.8), 8),
              'y': tabulated(lambda p: .22*math.cos(2*TAU*p), 8)}))
    out.append(score('lfo_reverse_swell', 'Reverse swell & aftershock', 'LFO II',
        'A long anticipatory rise, quick softened return, and two diminishing aftershocks.',
        axes={'y': keys([(0, 0), (3, -.82), (Fraction(7, 2), 0),
                         (4, -.38), (Fraction(9, 2), 0), (5, -.18),
                         (Fraction(11, 2), 0), (8, 0)]),
              'x': keys([(0, 0), (3, -.24), (Fraction(7, 2), .24), (6, 0), (8, 0)])}))
    return out


def path_scores():
    out = []
    def add(name, title, desc, funcs, period=8, **meta):
        out.append(score(name, title, 'Geometry', desc, period,
                   axes={axis: tabulated(fn, period) for axis, fn in funcs.items()}, **meta))
    add('path_lissajous_2_3', 'Two-by-three weave',
        'Two horizontal cycles cross three vertical cycles in a closed eight-beat Lissajous path.',
        {'x': lambda p: .78*math.sin(2*TAU*p), 'y': lambda p: .68*math.sin(3*TAU*p)})
    add('path_rose_4', 'Four-petal rose',
        'A signed radial oscillation draws four petals, passing through the centre between them.',
        {'x': lambda p: .82*math.cos(2*TAU*p)*math.cos(TAU*p),
         'y': lambda p: .82*math.cos(2*TAU*p)*math.sin(TAU*p)})
    add('path_rose_5', 'Five-petal rose',
        'Five petals in one complete eight-beat traversal; the odd-petal parameter runs through pi, not two pi.',
        {'x': lambda p: .82*math.cos(5*math.pi*p)*math.cos(math.pi*p),
         'y': lambda p: .82*math.cos(5*math.pi*p)*math.sin(math.pi*p)})
    add('path_bowed_diamond', 'Bowed diamond',
        'An astroid-shaped loop with inward-curved edges and naturally slow corners.',
        {'x': lambda p: .8*math.cos(TAU*p)**3, 'y': lambda p: .8*math.sin(TAU*p)**3})
    def eased_angle(p):
        return TAU*p-math.sin(TAU*p)
    add('path_orbit_dwell', 'Orbit with downbeat dwell',
        'An ellipse whose phase slows to zero speed at the loop boundary and accelerates through the opposite side.',
        {'x': lambda p: .8*math.cos(eased_angle(p)),
         'y': lambda p: .6*math.sin(eased_angle(p))})
    add('path_torus_knot', 'Three-dimensional torus knot',
        'Two turns around the axis and three through the tube. XYZ is retained; the demo projects depth.',
        {'x': lambda p: (.54+.22*math.cos(3*TAU*p))*math.cos(2*TAU*p),
         'y': lambda p: (.54+.22*math.cos(3*TAU*p))*math.sin(2*TAU*p),
         'z': lambda p: .36*math.sin(3*TAU*p)}, period=16)
    add('path_woven_3d', 'Two-three-five spatial weave',
        'Independent two-, three-, and five-cycle XYZ oscillations close after sixteen beats.',
        {'x': lambda p: .72*math.sin(2*TAU*p), 'y': lambda p: .64*math.sin(3*TAU*p),
         'z': lambda p: .48*math.sin(5*TAU*p)}, period=16)
    add('path_crank_slider', 'Slider & crank',
        'Horizontal slider-crank travel with rod length three and crank radius one; vertical motion follows the crank tip.',
        {'x': lambda p: .78*(math.cos(TAU*p)+math.sqrt(9-math.sin(TAU*p)**2)-3),
         'y': lambda p: .3*math.sin(TAU*p)}, period=4,
        equation='x=.78*(cos(theta)+sqrt(9-sin(theta)^2)-3); y=.3*sin(theta)')
    return out


def rhythm_scores():
    out = []
    g = {'right': gesture(.72, 0), 'left': gesture(-.72, 0),
         'down': gesture(0, .68), 'up': gesture(0, -.68)}
    for pulses in (5, 7):
        ev = [event(Fraction(4*i, pulses), 'right' if i % 2 == 0 else 'left',
                    duration=Fraction(3, 8)) for i in range(2*pulses)]
        ev += [event(i, 'down' if i % 2 == 0 else 'up', duration=Fraction(3, 8)) for i in range(8)]
        out.append(score('rhythm_%s_four' % ('five' if pulses == 5 else 'seven'),
                   f'{pulses} against four', 'Interlock',
                   f'{pulses} lateral hits against four vertical hits per four beats; two bars preserve alternating directions.',
                   events=ev, gestures=g, pulse_ratio=f'{pulses}:4',
                   base_cycle_beats='4', cycles=2))
    for pulses in (7, 5):
        positions = [i for i in range(16) if (i*pulses) % 16 < pulses]
        beats = [Fraction(i, 4)+4*cycle for cycle in range(2) for i in positions]
        ev = [event(t, 'right' if i % 2 == 0 else 'left',
                    1 if t.denominator == 1 else .72, Fraction(3, 8)) for i, t in enumerate(beats)]
        out.append(score(f'rhythm_euclid_{pulses}_16', f'{pulses} in sixteen', 'Interlock',
                   f'{pulses} evenly distributed onsets on a sixteen-step grid, repeated with alternating sides over eight beats.',
                   events=ev, gestures={'right': gesture(.76, -.3), 'left': gesture(-.76, -.3)},
                   algorithm='(step * pulses) % steps < pulses', steps=16, pulses=pulses,
                   base_cycle_beats='4', cycles=2))
    beats = [Fraction(i)+f for i in range(4) for f in (Fraction(0), Fraction(2, 3))]
    out.append(score('rhythm_swung_answer', 'Swung call & response', 'Interlock',
        'A two-to-one swung call on the right, answered on the left; four beats and eight peak-aligned gestures.', 4,
        events=[event(t, 'right' if t < 2 else 'left', 1 if t.denominator == 1 else .6,
                      Fraction(1, 4)) for t in beats],
        gestures={'right': gesture(.78, -.3), 'left': gesture(-.78, -.3)}, swing_ratio='2:1'))
    beats = [t+4*c for c in range(2) for t in (Fraction(0), Fraction(3, 2), Fraction(3))]
    out.append(score('rhythm_group_332', 'Three-three-two accents', 'Interlock',
        'Groups of three, three, and two eighth notes. Six alternating accents make an eight-beat loop.',
        events=[event(t, 'right' if i % 2 == 0 else 'left', (1, .72, .86)[i % 3]) for i, t in enumerate(beats)],
        gestures={'right': gesture(.76, -.38), 'left': gesture(-.76, -.38)}, grouping=[3, 3, 2], unit_beats='1/2'))
    beats = [t+Fraction(7, 2)*c for c in range(2) for t in (Fraction(0), Fraction(1), Fraction(2))]
    out.append(score('rhythm_group_223', 'Two-two-three stepping', 'Interlock',
        'Two 7/8 bars grouped as 2+2+3 eighth notes: a seven-quarter-note loop, not forced into four beats.', 7,
        events=[event(t, 'right' if i % 2 == 0 else 'left', (1, .7, .85)[i % 3]) for i, t in enumerate(beats)],
        gestures={'right': gesture(.74, -.4), 'left': gesture(-.74, -.4)}, grouping=[2, 2, 3],
        meter=[7, 8], bars=2, unit_beats='1/2'))
    ev = [event(Fraction(8*i, count), axis, duration=Fraction(3, 4))
          for axis, count in (('x', 3), ('y', 4), ('z', 5)) for i in range(count)]
    out.append(score('rhythm_three_four_five', 'Three-four-five interlock', 'Interlock',
        'Three X, four Y, and five Z gestures share an eight-beat phrase, with exact rational peak times.',
        events=ev, gestures={'x': gesture(x=.7), 'y': gesture(y=-.7), 'z': gesture(z=.55)},
        pulse_ratio='3:4:5', base_cycle_beats='8', cycles=1))
    return out


def document():
    return dict(format='dancerudiments.score-pack', schema_version=1,
                patterns=lfo_scores()+path_scores()+rhythm_scores())
