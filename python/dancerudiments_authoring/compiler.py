"""Compile curves + gestures to bounded, exact-pip C++ playback data."""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
import math

from ._validation import (BUILTIN_NAMES, MAX_PACK_SAMPLES, MAX_PATTERNS, MAX_SAMPLES, PIPS_PER_BEAT, ScoreError, beat,
                          canonical_json, choice, fields, integer, name, sequence, text)
from .curves import build_curve
from .events import build_events
from .model import CompiledPack, CompiledPattern


def compile_score(score: dict) -> CompiledPattern:
    fields(score, {'name', 'description', 'period_beats', 'tracks', 'gestures', 'events',
                   'bounds', 'loop_policy', 'provenance'}, {'name', 'period_beats'}, 'score')
    identifier = name(score['name'])
    description = text(score.get('description', ''), 'description')
    loop = beat(score['period_beats'], 'period_beats')
    period_pips = loop * PIPS_PER_BEAT
    if period_pips.denominator != 1 or not 1 <= period_pips <= MAX_SAMPLES:
        raise ScoreError('period_beats * 64 must be an integer in [1, 65535]; '
                         'enlarge the enclosing loop rather than rounding tuplets')
    count = int(period_pips)
    bounds = choice(score.get('bounds', 'reject'), ('reject', 'scale', 'clip'), 'bounds')
    policy = choice(score.get('loop_policy', 'closed'), ('closed', 'allow_jump'), 'loop_policy')
    provenance = score.get('provenance', {})
    if not isinstance(provenance, dict):
        raise ScoreError('provenance: expected an object')
    budget = [0]
    tracks = []
    for i, track in enumerate(sequence(score.get('tracks', []), 0, 64, 'tracks')):
        fields(track, {'axis', 'curve'}, {'axis', 'curve'}, f'tracks[{i}]')
        axis = choice(track['axis'], ('x', 'y', 'z'), f'tracks[{i}].axis')
        curve = build_curve(track['curve'], loop, budget, f'tracks[{i}].curve')
        tracks.append(('xyz'.index(axis), curve))
    events = build_events(score.get('gestures', {}), score.get('events', []), loop)
    if not tracks and not events:
        raise ScoreError('score: provide at least one curve track or event')
    if count * (budget[0] + len(events)) > 5_000_000:
        raise ScoreError('score: compilation work exceeds 5 million sample/node evaluations')
    active_events = [False] * len(events)

    def evaluate(t: Fraction, record: bool = False) -> tuple[float, float, float]:
        parts = [[], [], []]
        for axis, curve in tracks:
            parts[axis].append(curve(t))
        for i, event in enumerate(events):
            v = event.value(t, loop)
            if record and any(x != 0 for x in v):
                active_events[i] = True
            for axis in range(3):
                parts[axis].append(v[axis])
        value = tuple(math.fsum(p) for p in parts)
        if not all(math.isfinite(x) for x in value):
            raise ScoreError('Curves/events produced non-finite values')
        return value

    try:
        raw = [evaluate(Fraction(pip, PIPS_PER_BEAT), True) for pip in range(count)]
        # Check the left-hand limit, not the last sample (which is one pip before
        # the seam). Modulo at the exact endpoint would conceal a reset jump.
        left = evaluate(loop - loop / 10**12)
        right = raw[0]
        peak = max(abs(x) for row in raw + [left] for x in row)
    except ScoreError:
        raise
    except (OverflowError, ZeroDivisionError, ValueError) as exc:
        raise ScoreError('Curve arithmetic overflowed') from exc
    warnings = []
    scale = 1.0
    if bounds == 'reject' and peak > 1 + 1e-12:
        raise ScoreError(f'Output exceeds [-1, 1] (peak {peak:g}); reduce gains or choose bounds=scale/clip')
    if bounds == 'scale' and peak > 1:
        scale = 1 / peak
    if bounds == 'clip' and peak > 1:
        warnings.append('Clipping changes the curve shape; peak exceeded 1')

    def bounded(row: tuple) -> tuple:
        return tuple(max(-1.0, min(1.0, x*scale)) for x in row)

    left, right = bounded(left), bounded(right)
    seam_error = max(abs(a-b) for a, b in zip(left, right))
    if policy == 'closed' and seam_error > 1e-7:
        raise ScoreError(f'Loop has a position reset ({seam_error:g}); close the curve or '
                         'explicitly set loop_policy=allow_jump')
    if seam_error > 1e-7:
        warnings.append('Loop contains an explicitly allowed position reset')
    # Bake once; the exact exported decimals, not host math libraries, are the
    # runtime authority. Rounding stabilizes insignificant libm tail differences.
    samples = tuple(tuple(0.0 if abs(x) < 0.5e-12 else round(x, 12) for x in bounded(row))
                    for row in raw)
    steps = [math.dist(samples[i-1], samples[i]) for i in range(count)]
    if max(steps) > 0.5:
        warnings.append('Large per-pip movement (>0.5); check amplitude, rate and discontinuities')
    for i, event in enumerate(events):
        if event.duration * PIPS_PER_BEAT < 2:
            warnings.append(f'Event {i} is shorter than two pips and may be undersampled')
        if event.strength and any(event.axes) and not active_events[i]:
            warnings.append(f'Event {i} has no nonzero sample on the pip grid')
    diagnostics = {'seam_position_error': seam_error, 'seam_step': steps[0],
                   'max_step': max(steps), 'unscaled_peak_component': peak,
                   'normalization_scale': scale, 'loop_policy': policy, 'bounds': bounds,
                   'beat_unit': 'quarter_note', 'warnings': warnings}
    source_hash = sha256(canonical_json(score).encode('utf-8')).hexdigest()
    return CompiledPattern(identifier, description, count, samples, source_hash,
                           canonical_json(provenance), canonical_json(diagnostics))


def compile_pack(document: dict) -> CompiledPack:
    """Compile a versioned score pack, or one standalone score object."""
    if not isinstance(document, dict):
        raise ScoreError('Expected a score object or score-pack object')
    if 'format' not in document:
        return CompiledPack((compile_score(document),))
    keys = {'format', 'schema_version', 'patterns'}
    fields(document, keys, keys, 'score pack')
    if document['format'] != 'dancerudiments.score-pack':
        raise ScoreError('Expected dancerudiments.score-pack')
    integer(document['schema_version'], 1, 1, 'schema_version')
    scores = sequence(document['patterns'], 1, MAX_PATTERNS, 'patterns')
    # Reject oversized/duplicate packs before materializing all their tables.
    seen, total = set(BUILTIN_NAMES), 0
    for i, score in enumerate(scores):
        if not isinstance(score, dict):
            raise ScoreError(f'patterns[{i}]: expected a score object')
        identifier = name(score.get('name'), f'patterns[{i}].name')
        if identifier in seen:
            raise ScoreError(f'Duplicate or built-in pattern name: {identifier}')
        seen.add(identifier)
        size = beat(score.get('period_beats'), f'patterns[{i}].period_beats') * PIPS_PER_BEAT
        if size.denominator != 1 or not 1 <= size <= MAX_SAMPLES:
            raise ScoreError(f'patterns[{i}]: invalid enclosing loop period')
        total += int(size)
        if total > MAX_PACK_SAMPLES:
            raise ScoreError('Compiled pack exceeds the total sample limit')
    return CompiledPack(tuple(compile_score(s) for s in scores))
