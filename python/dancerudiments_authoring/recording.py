"""BPM-clocked, non-looping N-dimensional recordings. No Python playback engine."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from ._validation import (PIPS_PER_BEAT, MAX_SAMPLES, ScoreError, canonical_json,
                          fields, integer, name, number, sequence, choice, text)
from .io import read_json
from .model import CompiledPattern, CompiledPack

FORMAT = 'dancerudiments.recording'
MAX_RECORDING_VALUES = 8_388_608
MAX_JSON_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class RecordingClock:
    bpm: float
    bpm_source: str
    bpm_status: str = 'estimated'
    beat_zero_seconds: float = 0.0
    phase_status: str = 'unverified'
    start_pip: int = 0

    def __post_init__(self):
        bpm = number(self.bpm, 'bpm')
        if bpm <= 0 or not math.isfinite(60 / bpm) or 60 / bpm / PIPS_PER_BEAT <= 0:
            raise ScoreError('A positive, representable BPM estimate or confirmed value is required')
        object.__setattr__(self, 'bpm', bpm)
        if not text(self.bpm_source, 'bpm_source').strip():
            raise ScoreError('bpm_source is required')
        choice(self.bpm_status, ('estimated', 'confirmed'), 'bpm_status')
        choice(self.phase_status, ('unverified', 'estimated', 'supplied'), 'phase_status')
        object.__setattr__(self, 'beat_zero_seconds', number(self.beat_zero_seconds, 'beat_zero_seconds'))
        integer(self.start_pip, -2147483648, 2147483647, 'start_pip')

    @property
    def pip_seconds(self):
        return Fraction(60, PIPS_PER_BEAT) / Fraction(str(self.bpm))

    def time_seconds(self, index: int):
        integer(index, 0, MAX_RECORDING_VALUES, 'index')
        return float(Fraction(str(self.beat_zero_seconds)) + (self.start_pip + index) * self.pip_seconds)

    @classmethod
    def from_dict(cls, data):
        keys = {'bpm', 'bpm_source', 'bpm_status', 'beat_zero_seconds', 'phase_status', 'start_pip'}
        fields(data, keys, keys, 'clock')
        return cls(**data)


@dataclass(frozen=True)
class Recording:
    name: str
    dimensions: tuple[str, ...]
    samples: tuple[tuple[float, ...], ...]
    clock: RecordingClock
    provenance_json: str = '{}'

    def __post_init__(self):
        name(self.name)
        if not isinstance(self.clock, RecordingClock):
            raise ScoreError('A RecordingClock with BPM provenance is required')
        dims = tuple(sequence(self.dimensions, 1, MAX_RECORDING_VALUES, 'dimensions'))
        for dim in dims:
            name(dim, 'dimension')
        if len(set(dims)) != len(dims):
            raise ScoreError('Dimension names must be unique')
        rows = sequence(self.samples, 1, MAX_RECORDING_VALUES // len(dims), 'samples')
        if self.clock.start_pip + len(rows) > 2147483647:
            raise ScoreError('Recording exceeds the signed int32 pip range')
        frozen = []
        for row in rows:
            values = tuple(number(v, 'sample') for v in sequence(row, len(dims), len(dims), 'row'))
            if any(abs(v) > 1 for v in values):
                raise ScoreError('Samples must be in [-1,1]')
            frozen.append(tuple(round(v, 12) for v in values))
        object.__setattr__(self, 'dimensions', dims)
        object.__setattr__(self, 'samples', tuple(frozen))
        try:
            meta = json.loads(self.provenance_json)
        except (ValueError, TypeError, RecursionError) as exc:
            raise ScoreError('provenance_json must be a finite JSON object') from exc
        if not isinstance(meta, dict):
            raise ScoreError('provenance_json must be an object')
        object.__setattr__(self, 'provenance_json', canonical_json(meta))

    @property
    def provenance(self):
        return json.loads(self.provenance_json)

    def to_dict(self):
        return dict(format=FORMAT, schema_version=1, pips_per_beat=PIPS_PER_BEAT,
                    sample_dtype='float64', sample_decimals=12, name=self.name,
                    dimensions=list(self.dimensions), samples=[list(r) for r in self.samples],
                    clock=asdict(self.clock), provenance=self.provenance)

    @classmethod
    def from_dict(cls, data):
        keys = {'format', 'schema_version', 'pips_per_beat', 'sample_dtype', 'sample_decimals',
                'name', 'dimensions', 'samples', 'clock', 'provenance'}
        fields(data, keys, keys, 'recording')
        choice(data['format'], (FORMAT,), 'format')
        choice(data['sample_dtype'], ('float64',), 'sample_dtype')
        for key, value in [('schema_version', 1), ('pips_per_beat', 64), ('sample_decimals', 12)]:
            integer(data[key], value, value, key)
        return cls(data['name'], data['dimensions'], data['samples'],
                   RecordingClock.from_dict(data['clock']), canonical_json(data['provenance']))

    def to_native(self):
        try:
            from dancerudiments import SampledRecording
        except ImportError as exc:
            raise RuntimeError('Install/rebuild the DanceRudiments native recording update') from exc
        return SampledRecording(self.name, self.dimensions, self.samples, self.clock.bpm,
                                self.clock.beat_zero_seconds, self.clock.start_pip)

    def to_compiled_pack(self, *, dimensions=None, start=0, count=None):
        dims = tuple(self.dimensions if dimensions is None else dimensions)
        if not 1 <= len(dims) <= 3 or len(set(dims)) != len(dims) or any(d not in self.dimensions for d in dims):
            raise ScoreError('Legacy export requires an explicit selection of 1..3 unique dimensions')
        integer(start, 0, len(self.samples) - 1, 'start')
        count = len(self.samples) - start if count is None else count
        integer(count, 1, min(MAX_SAMPLES, len(self.samples) - start), 'count')
        indices = [self.dimensions.index(d) for d in dims]
        rows = tuple(tuple(row[i] for i in indices) + (0.,) * (3-len(dims))
                     for row in self.samples[start:start+count])
        digest = hashlib.sha256(canonical_json(self.to_dict()).encode()).hexdigest()
        meta = dict(self.provenance, recording_clock=asdict(self.clock),
                    selected_dimensions=list(dims), recording_start_pip=self.clock.start_pip + start)
        diagnostics = {'loop_policy': 'allow_jump', 'warnings': ['Legacy playback loops this excerpt; its seam has not been repaired.']}
        return CompiledPack((CompiledPattern(self.name, 'Audio-derived recording excerpt', count,
                    rows, digest, canonical_json(meta), canonical_json(diagnostics)),))


def load_recording(path):
    return Recording.from_dict(read_json(path))


def write_document(path, document, *, overwrite=False):
    if document.get('format') == FORMAT:
        document = Recording.from_dict(document).to_dict()
    else:
        document = CompiledPack.from_dict(document).to_dict()
    _write_json_document(path, document, overwrite=overwrite)


def _write_json_document(path, document, *, overwrite=False):
    """Atomically write a caller-validated, finite JSON document without clobbering."""
    payload = canonical_json(document).encode('ascii') + b'\n'
    if len(payload) > MAX_JSON_BYTES:
        raise ScoreError('JSON exceeds 64 MiB; export a shorter excerpt')
    _write_bytes_document(path, payload, overwrite=overwrite)


def _write_bytes_document(path, payload, *, overwrite=False):
    """Shared atomic output for validated JSON and its CSV channel reference."""
    if not isinstance(payload, bytes) or len(payload) > MAX_JSON_BYTES:
        raise ScoreError('Output must be bytes within the 64 MiB document limit')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.recording-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if overwrite:
            os.replace(tmp, path)
        else:
            os.link(tmp, path)  # atomic, refuses an existing target
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_recording(path, recording, *, overwrite=False):
    write_document(path, recording.to_dict(), overwrite=overwrite)
