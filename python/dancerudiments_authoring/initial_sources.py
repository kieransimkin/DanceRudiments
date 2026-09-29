"""Bounded, standard-library adapters used to rebuild the initial audition pack.

Conversion only. Runtime movement sampling remains in C++.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha1, sha256
import re
import struct


@dataclass(frozen=True)
class MidiHit:
    tick: int
    note: int
    velocity: int
    channel: int


@dataclass(frozen=True)
class MidiScore:
    ppq: int
    hits: tuple[MidiHit, ...]
    tempos: tuple[tuple[int, int], ...]
    meters: tuple[tuple[int, int, int], ...]


def verify_blob(data: bytes, expected: str) -> str:
    """Verify the exact Git blob identity; return a transport-independent SHA-256."""
    actual = sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
    if actual != expected:
        raise ValueError(f'Source checksum mismatch: expected {expected}, got {actual}')
    return sha256(data).hexdigest()


def read_akwf_header(data: bytes) -> tuple[int, ...]:
    """Read the numeric 256-entry int16 table, never execute the C/C++ file."""
    if len(data) > 65536:
        raise ValueError('AKWF header exceeds 64 KiB')
    text = data.decode('utf-8')
    match = re.search(r'const\s+int16_t\s+\w+\s*\[\s*256\s*\]\s*=\s*\{([^{}]+)\}\s*;', text)
    if not match or not re.fullmatch(r'[\s,0-9+\-]+', match.group(1)):
        raise ValueError('Expected a literal int16_t[256] table')
    fields = match.group(1).strip().rstrip(',').split(',')
    values = tuple(int(x.strip()) for x in fields)
    if len(values) != 256 or any(not -32768 <= x <= 32767 for x in values):
        raise ValueError('Expected 256 signed 16-bit values')
    return values


def smooth_periodic(values: tuple[int, ...], passes: int = 8) -> list[float]:
    """Symmetric circular [1/4, 1/2, 1/4] FIR; then remove DC and scale to .85."""
    if not values or not 0 <= passes <= 64:
        raise ValueError('Invalid smoothing input')
    result = [float(v) for v in values]
    for _ in range(passes):
        result = [(result[i-1] + 2*x + result[(i+1) % len(result)]) / 4
                  for i, x in enumerate(result)]
    dc = sum(result) / len(result)
    result = [v-dc for v in result]
    peak = max(abs(v) for v in result)
    if peak == 0:
        raise ValueError('Constant waveform cannot be normalised')
    return [v * .85 / peak for v in result]


class _Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def take(self, count: int) -> bytes:
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError('Truncated MIDI data')
        result = self.data[self.pos:self.pos+count]
        self.pos += count
        return result

    def byte(self) -> int:
        return self.take(1)[0]

    def vlq(self) -> int:
        value = 0
        for _ in range(4):
            b = self.byte()
            value = (value << 7) | (b & 127)
            if not b & 128:
                return value
        raise ValueError('MIDI variable-length quantity exceeds four bytes')


def read_midi(data: bytes) -> MidiScore:
    """Read SMF format 0/1, PPQ note-ons and timing metadata. Not a MIDI player.

    Only positive-velocity note-ons are emitted. Note-offs/controllers are
    parsed but do not become movement events. SMPTE and format 2 are rejected.
    """
    if len(data) > 16 * 1024 * 1024:
        raise ValueError('MIDI input exceeds 16 MiB')
    reader = _Reader(data)
    if reader.take(4) != b'MThd':
        raise ValueError('Missing MThd')
    size = int.from_bytes(reader.take(4), 'big')
    if size < 6:
        raise ValueError('Invalid MIDI header')
    fmt, tracks, ppq = struct.unpack('>HHH', reader.take(6))
    reader.take(size-6)
    if fmt not in (0, 1) or not 1 <= tracks <= 256 or (fmt == 0 and tracks != 1):
        raise ValueError('Expected SMF format 0/1 and 1..256 tracks')
    if ppq == 0 or ppq & 0x8000:
        raise ValueError('Only positive PPQ division is supported, not SMPTE')
    hits, tempos, meters = [], [], []
    for _ in range(tracks):
        if reader.take(4) != b'MTrk':
            raise ValueError('Missing MTrk')
        track = _Reader(reader.take(int.from_bytes(reader.take(4), 'big')))
        tick, running, ended = 0, None, False
        while track.pos < len(track.data):
            tick += track.vlq()
            status = track.byte()
            first = None
            if status < 0x80:
                if running is None:
                    raise ValueError('Running status without a channel status')
                first, status = status, running
            if 0x80 <= status <= 0xEF:
                running = status
                count = 1 if status >> 4 in (0xC, 0xD) else 2
                payload = ([first] if first is not None else [])
                payload += list(track.take(count-len(payload)))
                if any(b >= 0x80 for b in payload):
                    raise ValueError('Invalid channel data byte')
                if status >> 4 == 9 and payload[1] > 0:
                    hits.append(MidiHit(tick, payload[0], payload[1], status & 15))
            elif status == 0xFF:
                running = None
                kind = track.byte()
                payload = track.take(track.vlq())
                if kind == 0x2F:
                    if payload or track.pos != len(track.data):
                        raise ValueError('Invalid end-of-track')
                    ended = True
                    break
                if kind == 0x51:
                    if len(payload) != 3 or int.from_bytes(payload, 'big') == 0:
                        raise ValueError('Invalid MIDI tempo')
                    tempos.append((tick, int.from_bytes(payload, 'big')))
                if kind == 0x58:
                    if len(payload) != 4 or payload[0] == 0 or payload[1] > 7:
                        raise ValueError('Invalid time signature')
                    meters.append((tick, payload[0], 1 << payload[1]))
            elif status in (0xF0, 0xF7):
                running = None
                track.take(track.vlq())
            else:
                raise ValueError(f'Unsupported SMF event status 0x{status:02x}')
            if len(hits) > 100000:
                raise ValueError('Too many MIDI note-ons')
        if not ended:
            raise ValueError('Missing end-of-track')
    if reader.pos != len(data):
        raise ValueError('Unexpected trailing MIDI data')
    return MidiScore(ppq, tuple(sorted(hits, key=lambda h: (h.tick, h.channel, h.note))),
                     tuple(sorted(tempos)), tuple(sorted(meters)))


def nearest_sixteenth(beat: Fraction) -> Fraction:
    """Nearest quarter-beat; exact halfway values round towards +infinity."""
    n = beat * 4 + Fraction(1, 2)
    return Fraction(n.numerator // n.denominator, 4)


def excerpt_hits(midi: MidiScore, start: int, length: int, quantise: bool = False):
    """Select on nearest-sixteenth ownership, preserve anticipations modulo loop.

    A kick a tick before the first downbeat belongs to this excerpt but its
    played phase remains a tick before the loop seam. Both variants use the
    exact same hits and velocities. No duplicate events are merged.
    """
    result = []
    for hit in midi.hits:
        position = Fraction(hit.tick, midi.ppq)
        grid = nearest_sixteenth(position)
        if hit.channel == 9 and start <= grid < start + length:
            result.append(((grid if quantise else position) - start, hit))
    return [((t % length), h) for t, h in result]
