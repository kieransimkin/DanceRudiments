"""Offline scalar curve builders. These functions are not a playback fallback."""
from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction
from hashlib import sha256
import math
from typing import Callable

from ._validation import ScoreError, beat, choice, fields, integer, number, sequence

Curve = Callable[[Fraction], float]


def smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def build_curve(spec: dict, loop: Fraction, budget: list[int], path: str = 'curve',
                depth: int = 0) -> Curve:
    """Build an offline evaluator with absolute rational beat positions."""
    budget[0] += 1
    if depth > 16 or budget[0] > 4096:
        raise ScoreError(f'{path}: curve graph exceeds complexity limit')
    if not isinstance(spec, dict):
        raise ScoreError(f'{path}: expected a curve object')
    kind = choice(spec.get('type'), ('constant', 'lfo', 'keyframes', 'samples',
                                    'random_hold', 'random_smooth', 'sum', 'product', 'mix'), path)
    common = {'type', 'gain', 'offset'}
    options = {
        'constant': {'value'},
        'lfo': {'shape', 'period_beats', 'phase', 'duty'},
        'keyframes': {'points'},
        'samples': {'values', 'period_beats', 'phase', 'interpolation'},
        'random_hold': {'steps', 'seed', 'period_beats', 'phase'},
        'random_smooth': {'steps', 'seed', 'period_beats', 'phase'},
        'sum': {'curves'}, 'product': {'curves'}, 'mix': {'a', 'b', 'amount'},
    }
    required = {'constant': {'value'}, 'keyframes': {'points'}, 'samples': {'values'},
                'sum': {'curves'}, 'product': {'curves'}, 'mix': {'a', 'b', 'amount'}}
    fields(spec, common | options[kind], {'type'} | required.get(kind, set()), path)
    gain = number(spec.get('gain', 1), path + '.gain')
    offset = number(spec.get('offset', 0), path + '.offset')

    def child(value: dict, suffix: str) -> Curve:
        return build_curve(value, loop, budget, path + suffix, depth + 1)

    if kind == 'constant':
        value = number(spec['value'], path + '.value')
        raw = lambda t: value
    elif kind == 'keyframes':
        points = sequence(spec['points'], 2, 4096, path + '.points')
        times, values, modes, controls = [], [], [], []
        for i, point in enumerate(points):
            pp = f'{path}.points[{i}]'
            fields(point, {'beat', 'value', 'interpolation', 'control1', 'control2'},
                   {'beat', 'value'}, pp)
            times.append(beat(point['beat'], pp + '.beat'))
            values.append(number(point['value'], pp + '.value'))
            mode = choice(point.get('interpolation', 'smoothstep'),
                          ('linear', 'hold', 'smoothstep', 'smootherstep', 'cubic'), pp)
            if mode == 'cubic':
                if i == len(points) - 1:
                    raise ScoreError(f'{pp}: last point cannot start a cubic segment')
                controls.append((number(point.get('control1'), pp + '.control1'),
                                 number(point.get('control2'), pp + '.control2')))
            else:
                if 'control1' in point or 'control2' in point:
                    raise ScoreError(f'{pp}: controls require cubic interpolation')
                controls.append((0.0, 0.0))
            modes.append(mode)
        if times[0] != 0 or times[-1] != loop or any(a >= b for a, b in zip(times, times[1:])):
            raise ScoreError(f'{path}: keyframe beats must increase strictly from 0 to period_beats')

        def raw(t: Fraction) -> float:
            if t == loop:
                return values[-1]
            i = max(0, min(len(times) - 2, bisect_right(times, t) - 1))
            u = float((t - times[i]) / (times[i + 1] - times[i]))
            a, b, mode = values[i], values[i + 1], modes[i]
            if mode == 'hold':
                return a
            if mode == 'cubic':
                c1, c2 = controls[i]
                return (1-u)**3*a + 3*(1-u)**2*u*c1 + 3*(1-u)*u*u*c2 + u**3*b
            if mode == 'smoothstep':
                u = smooth(u)
            elif mode == 'smootherstep':
                u = u*u*u*(u*(u*6-15)+10)
            return a + (b-a)*u
    elif kind in ('sum', 'product'):
        children = [child(c, f'.curves[{i}]') for i, c in enumerate(
            sequence(spec['curves'], 1, 32, path + '.curves'))]
        if kind == 'sum':
            raw = lambda t: math.fsum(c(t) for c in children)
        else:
            raw = lambda t: math.prod(c(t) for c in children)
    elif kind == 'mix':
        a, b = child(spec['a'], '.a'), child(spec['b'], '.b')
        amount_spec = spec['amount']
        if isinstance(amount_spec, dict):
            amount = child(amount_spec, '.amount')
        else:
            fixed = number(amount_spec, path + '.amount')
            amount = lambda t: fixed

        def raw(t: Fraction) -> float:
            u = amount(t)
            if not math.isfinite(u) or not 0 <= u <= 1:
                raise ScoreError(f'{path}.amount: mix amount must be in [0, 1]')
            return (1-u)*a(t) + u*b(t)
    else:
        period = beat(spec.get('period_beats', str(loop)), path + '.period_beats')
        phase = beat(spec.get('phase', 0), path + '.phase')
        if period <= 0:
            raise ScoreError(f'{path}: period_beats must be positive')
        # No accumulated floating-point phase and no integer duration rounding.
        def phase_at(t: Fraction) -> Fraction:
            return (t / period + phase) % 1

        if kind == 'lfo':
            shape = choice(spec.get('shape', 'sine'), ('sine', 'triangle', 'saw_up',
                           'saw_down', 'pulse', 'skew_triangle'), path + '.shape')
            duty = number(spec.get('duty', 0.5), path + '.duty')
            if not 0 < duty < 1:
                raise ScoreError(f'{path}.duty: must lie strictly between 0 and 1')

            def raw(t: Fraction) -> float:
                p = float(phase_at(t))
                if shape == 'sine':
                    return math.sin(2 * math.pi * p)
                if shape == 'triangle':
                    return 1 - 4 * abs(p - 0.5)
                if shape == 'saw_up':
                    return 2*p - 1
                if shape == 'saw_down':
                    return 1 - 2*p
                if shape == 'pulse':
                    return 1.0 if p < duty else -1.0
                return -1 + 2*p/duty if p < duty else 1 - 2*(p-duty)/(1-duty)
        else:
            if kind == 'samples':
                values = [number(v, path + '.values') for v in
                          sequence(spec['values'], 2, 4096, path + '.values')]
                interpolation = choice(spec.get('interpolation', 'linear'),
                                       ('linear', 'hold', 'smoothstep'), path + '.interpolation')
            else:
                count = integer(spec.get('steps', 8), 1, 4096, path + '.steps')
                seed = integer(spec.get('seed', 0), -(2**63), 2**63-1, path + '.seed')
                # Fixed hash algorithm, unlike process-randomized Python hash().
                values = [2 * (int.from_bytes(sha256(
                    f'dancerudiments:v1:{seed}:{i}'.encode('ascii')).digest()[:8], 'big') /
                    (2**64 - 1)) - 1 for i in range(count)]
                interpolation = 'hold' if kind == 'random_hold' else 'smoothstep'

            def raw(t: Fraction) -> float:
                p = phase_at(t) * len(values)
                i = p.numerator // p.denominator
                u = float(p-i)
                if interpolation == 'hold':
                    return values[i]
                if interpolation == 'smoothstep':
                    u = smooth(u)
                return values[i] + (values[(i+1) % len(values)] - values[i])*u

    return lambda t: offset + gain * raw(t)
