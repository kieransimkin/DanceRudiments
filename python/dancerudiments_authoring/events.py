"""Rational-beat event scores mapped to explicitly anchored periodic gestures."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math

from ._validation import ScoreError, beat, choice, fields, name, number, sequence
from .curves import smooth


@dataclass(frozen=True)
class GestureEvent:
    onset: Fraction
    duration: Fraction
    peak: Fraction
    axes: tuple[float, float, float]
    strength: float
    shape: str

    def value(self, t: Fraction, loop: Fraction) -> tuple[float, float, float]:
        delta = (t-self.onset) % loop
        if delta >= self.duration:
            return (0.0, 0.0, 0.0)
        p = delta / self.duration
        u = float(p/self.peak if p <= self.peak else (1-p)/(1-self.peak))
        if self.shape == 'cosine':
            u = 0.5 - 0.5 * math.cos(math.pi*u)
        elif self.shape == 'smoothstep':
            u = smooth(u)
        return tuple(v * self.strength * u for v in self.axes)


def build_events(gestures: dict, events: list, loop: Fraction) -> list[GestureEvent]:
    if not isinstance(gestures, dict) or len(gestures) > 256:
        raise ScoreError('gestures: expected an object with at most 256 gestures')
    validated = {}
    for key, gesture in gestures.items():
        name(key, 'gesture name')
        path = f'gestures.{key}'
        fields(gesture, {'duration_beats', 'peak_fraction', 'axes', 'shape'},
               {'duration_beats', 'axes'}, path)
        duration = beat(gesture['duration_beats'], path + '.duration_beats')
        peak = beat(gesture.get('peak_fraction', '1/2'), path + '.peak_fraction')
        if not 0 < duration <= loop or not 0 < peak < 1:
            raise ScoreError(f'{path}: require 0 < duration <= loop and 0 < peak_fraction < 1')
        axes = fields(gesture['axes'], {'x', 'y', 'z'}, set(), path + '.axes')
        if not axes:
            raise ScoreError(f'{path}.axes: specify at least one axis')
        vector = tuple(number(axes.get(axis, 0), path + '.' + axis) for axis in 'xyz')
        shape = choice(gesture.get('shape', 'cosine'), ('cosine', 'triangle', 'smoothstep'), path)
        validated[key] = (duration, peak, vector, shape)
    result = []
    for i, event in enumerate(sequence(events, 0, 4096, 'events')):
        path = f'events[{i}]'
        fields(event, {'beat', 'gesture', 'anchor', 'strength', 'duration_beats'},
               {'beat', 'gesture'}, path)
        key = name(event['gesture'], path + '.gesture')
        if key not in validated:
            raise ScoreError(f'{path}: unknown gesture {key!r}')
        duration, peak, vector, shape = validated[key]
        duration = beat(event.get('duration_beats', duration), path + '.duration_beats')
        t = beat(event['beat'], path + '.beat')
        if not 0 <= t < loop or not 0 < duration <= loop:
            raise ScoreError(f'{path}: beat must lie in [0, loop); duration in (0, loop]')
        anchor = choice(event.get('anchor', 'onset'), ('onset', 'peak', 'end'), path + '.anchor')
        anchor_fraction = {'onset': Fraction(0), 'peak': peak, 'end': Fraction(1)}[anchor]
        strength = number(event.get('strength', 1), path + '.strength')
        if strength < 0:
            raise ScoreError(f'{path}.strength: cannot be negative (invert the axis instead)')
        result.append(GestureEvent((t-duration*anchor_fraction) % loop,
                                   duration, peak, vector, strength, shape))
    return result
