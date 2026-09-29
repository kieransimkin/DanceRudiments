"""Validated compiled data. Runtime movement is delegated exclusively to C++."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from ._validation import (BUILTIN_NAMES, MAX_PACK_SAMPLES, MAX_PATTERNS, MAX_SAMPLES,
                          PIPS_PER_BEAT, ScoreError, canonical_json, fields, integer,
                          name, number, sequence, text)


@dataclass(frozen=True)
class CompiledPattern:
    name: str
    description: str
    period_pips: int
    samples: tuple[tuple[float, float, float], ...]
    source_sha256: str
    provenance_json: str = '{}'
    diagnostics_json: str = '{}'

    def __post_init__(self) -> None:
        name(self.name)
        text(self.description, 'description')
        integer(self.period_pips, 1, MAX_SAMPLES, 'period_pips')
        values = sequence(self.samples, self.period_pips, self.period_pips, 'samples')
        frozen = []
        for i, row in enumerate(values):
            row = sequence(row, 3, 3, f'samples[{i}]')
            v = tuple(number(x, f'samples[{i}]') for x in row)
            if any(abs(x) > 1 for x in v):
                raise ScoreError(f'samples[{i}]: components must be within [-1, 1]')
            frozen.append(v)
        object.__setattr__(self, 'samples', tuple(frozen))
        if not isinstance(self.source_sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.source_sha256):
            raise ScoreError('source_sha256: expected a lowercase SHA-256 hex digest')
        for attr in ('provenance_json', 'diagnostics_json'):
            try:
                value = json.loads(getattr(self, attr))
            except (ValueError, TypeError) as exc:
                raise ScoreError(f'{attr}: invalid JSON') from exc
            if not isinstance(value, dict):
                raise ScoreError(f'{attr}: expected a JSON object')
            object.__setattr__(self, attr, canonical_json(value))

    @property
    def provenance(self) -> dict:
        return json.loads(self.provenance_json)

    @property
    def diagnostics(self) -> dict:
        return json.loads(self.diagnostics_json)

    def to_dict(self) -> dict:
        return dict(name=self.name, description=self.description, period_pips=self.period_pips,
                    samples=[list(v) for v in self.samples], source_sha256=self.source_sha256,
                    provenance=self.provenance, diagnostics=self.diagnostics)

    @classmethod
    def from_dict(cls, data: dict) -> CompiledPattern:
        keys = {'name', 'description', 'period_pips', 'samples', 'source_sha256',
                'provenance', 'diagnostics'}
        fields(data, keys, keys, 'compiled pattern')
        return cls(data['name'], data['description'], data['period_pips'], data['samples'],
                   data['source_sha256'], canonical_json(data['provenance']),
                   canonical_json(data['diagnostics']))

    def to_native(self) -> Any:
        try:
            from dancerudiments import SampledPattern
        except ImportError as exc:
            raise RuntimeError('Install/rebuild the patched dancerudiments extension for playback; '
                               'authoring itself does not require it') from exc
        return SampledPattern(self.name, self.description, self.samples)


@dataclass(frozen=True)
class CompiledPack:
    patterns: tuple[CompiledPattern, ...]

    def __post_init__(self) -> None:
        patterns = sequence(self.patterns, 1, MAX_PATTERNS, 'patterns')
        seen = set(BUILTIN_NAMES)
        total = 0
        for p in patterns:
            if not isinstance(p, CompiledPattern):
                raise ScoreError('patterns: expected CompiledPattern objects')
            if p.name in seen:
                raise ScoreError(f'Duplicate or built-in pattern name: {p.name}')
            seen.add(p.name)
            total += p.period_pips
        if total > MAX_PACK_SAMPLES:
            raise ScoreError('Compiled pack exceeds the total sample limit')
        object.__setattr__(self, 'patterns', tuple(patterns))

    def to_dict(self) -> dict:
        return {'format': 'dancerudiments.compiled-pack', 'schema_version': 1,
                'pips_per_beat': PIPS_PER_BEAT, 'patterns': [p.to_dict() for p in self.patterns]}

    @classmethod
    def from_dict(cls, data: dict) -> CompiledPack:
        keys = {'format', 'schema_version', 'pips_per_beat', 'patterns'}
        fields(data, keys, keys, 'compiled pack')
        if data['format'] != 'dancerudiments.compiled-pack':
            raise ScoreError('Not a dancerudiments.compiled-pack')
        integer(data['schema_version'], 1, 1, 'schema_version')
        integer(data['pips_per_beat'], 64, 64, 'pips_per_beat')
        patterns = sequence(data['patterns'], 1, MAX_PATTERNS, 'patterns')
        return cls(tuple(CompiledPattern.from_dict(p) for p in patterns))

    def to_native(self) -> Any:
        try:
            from dancerudiments import PatternLibrary
        except ImportError as exc:
            raise RuntimeError('Install/rebuild the patched dancerudiments extension for playback') from exc
        return PatternLibrary([p.to_native() for p in self.patterns])
