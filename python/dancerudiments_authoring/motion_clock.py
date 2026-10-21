"""Explicit, invertible musical time maps for offline motion authoring.

The runtime still samples native integer pips.  This module maps an absolute
transport time to a pip; it never evaluates a movement or accumulates frame hops.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
import math

from ._validation import (PIPS_PER_BEAT, ScoreError, beat as fraction, choice,
                          fields, integer, sequence, text)

FORMAT = "dancerudiments.beat-map"
MAX_ANCHORS = 1_048_576


def _fraction(value, path):
    result = fraction(value, path)
    try:
        finite = math.isfinite(float(result))
    except OverflowError:
        finite = False
    if not finite:
        raise ScoreError(f"{path}: value is not representable as a finite time")
    return result


def _json_fraction(value):
    return value.numerator if value.denominator == 1 else str(value)


@dataclass(frozen=True)
class BeatAnchor:
    """A measured timestamp and its quarter-note beat position.

    Numbers have their decimal meaning; rational strings remain exact.  The
    public fields are Fractions, and serialize without rounding the source map.
    """

    seconds: Fraction
    beat: Fraction

    def __post_init__(self):
        object.__setattr__(self, "seconds", _fraction(self.seconds, "anchor.seconds"))
        object.__setattr__(self, "beat", _fraction(self.beat, "anchor.beat"))

    def to_dict(self):
        return {"seconds": _json_fraction(self.seconds), "beat": _json_fraction(self.beat)}

    @classmethod
    def from_dict(cls, value):
        fields(value, {"seconds", "beat"}, {"seconds", "beat"}, "anchor")
        return cls(value["seconds"], value["beat"])


@dataclass(frozen=True)
class BeatMap:
    """Piecewise linear beat position with a well-defined inverse.

    Anchors must increase strictly in both dimensions.  Measured maps are
    bounded by default.  ``from_bpm`` deliberately produces an unbounded linear
    map, because a supplied constant tempo defines that extrapolation.
    """

    anchors: tuple[BeatAnchor, ...]
    source: str
    bpm_status: str = "estimated"
    phase_status: str = "unverified"
    extrapolate: bool = False
    _seconds: tuple[Fraction, ...] = field(init=False, repr=False, compare=False)
    _beats: tuple[Fraction, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        raw = sequence(self.anchors, 2, MAX_ANCHORS, "anchors")
        anchors = []
        for anchor in raw:
            if isinstance(anchor, BeatAnchor):
                anchors.append(anchor)
            else:
                pair = sequence(anchor, 2, 2, "anchor")
                anchors.append(BeatAnchor(pair[0], pair[1]))
        if any(b.seconds <= a.seconds or b.beat <= a.beat
               for a, b in zip(anchors, anchors[1:])):
            raise ScoreError("Beat-map anchors must strictly increase in seconds and beats")
        if not text(self.source, "beat_map.source").strip():
            raise ScoreError("Beat-map timing provenance is required")
        choice(self.bpm_status, ("estimated", "confirmed"), "beat_map.bpm_status")
        choice(self.phase_status, ("unverified", "estimated", "supplied"), "beat_map.phase_status")
        if type(self.extrapolate) is not bool:
            raise ScoreError("beat_map.extrapolate must be a boolean")
        object.__setattr__(self, "anchors", tuple(anchors))
        object.__setattr__(self, "_seconds", tuple(a.seconds for a in anchors))
        object.__setattr__(self, "_beats", tuple(a.beat for a in anchors))

    @classmethod
    def from_bpm(cls, bpm, *, beat_zero_seconds, source,
                 bpm_status="estimated", phase_status="unverified"):
        """Construct a constant-tempo map, with an explicitly supplied origin."""
        tempo = _fraction(bpm, "bpm")
        origin = _fraction(beat_zero_seconds, "beat_zero_seconds")
        if tempo <= 0:
            raise ScoreError("A positive BPM is required")
        return cls((BeatAnchor(origin, 0), BeatAnchor(origin + 60 / tempo, 1)),
                   source, bpm_status, phase_status, True)

    def _interpolate(self, value, source, target, label):
        value = _fraction(value, label)
        if not self.extrapolate and not source[0] <= value <= source[-1]:
            raise ScoreError(f"{label} lies outside the measured beat map")
        index = min(max(bisect_right(source, value) - 1, 0), len(source) - 2)
        weight = (value - source[index]) / (source[index + 1] - source[index])
        return target[index] + weight * (target[index + 1] - target[index])

    def beat_fraction(self, seconds):
        """Exact beat position from decimal/rational transport seconds."""
        return self._interpolate(seconds, self._seconds, self._beats, "seconds")

    def seconds_fraction(self, beat):
        """Exact inverse; useful when a generated boundary must round-trip."""
        return self._interpolate(beat, self._beats, self._seconds, "beat")

    def beat_at(self, seconds):
        return float(self.beat_fraction(seconds))

    def seconds_at(self, beat):
        return float(self.seconds_fraction(beat))

    def pip_at(self, seconds):
        """Floor the absolute beat position, including negative times.

        No loop or clamping is implicit.  The caller uses this integer with the
        native recording sampler, which enforces the recording's own bounds.
        """
        pip = math.floor(self.beat_fraction(seconds) * PIPS_PER_BEAT)
        return integer(pip, -2147483648, 2147483647, "pip")

    def to_dict(self):
        return dict(format=FORMAT, schema_version=1, pips_per_beat=PIPS_PER_BEAT,
                    interpolation="linear", anchors=[a.to_dict() for a in self.anchors],
                    source=self.source, bpm_status=self.bpm_status,
                    phase_status=self.phase_status, extrapolate=self.extrapolate)

    @classmethod
    def from_dict(cls, value):
        keys = {"format", "schema_version", "pips_per_beat", "interpolation", "anchors",
                "source", "bpm_status", "phase_status", "extrapolate"}
        fields(value, keys, keys, "beat_map")
        choice(value["format"], (FORMAT,), "beat_map.format")
        integer(value["schema_version"], 1, 1, "beat_map.schema_version")
        integer(value["pips_per_beat"], PIPS_PER_BEAT, PIPS_PER_BEAT, "beat_map.pips_per_beat")
        choice(value["interpolation"], ("linear",), "beat_map.interpolation")
        anchors = sequence(value["anchors"], 2, MAX_ANCHORS, "beat_map.anchors")
        return cls(tuple(BeatAnchor.from_dict(a) for a in anchors), value["source"],
                   value["bpm_status"], value["phase_status"], value["extrapolate"])
