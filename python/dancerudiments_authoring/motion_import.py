"""Compile captured rig controls onto the existing 64-pip recording grid.

This is offline authoring, not a second playback engine.  Blender/other importers
must retarget foreign skeletons first, then capture the exact destination rig's
physical channels.  Only bounded, validated JSON is accepted here; no pickle,
embedded Python, arbitrary property evaluation or implicit clip downloads.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math

from ._validation import (PIPS_PER_BEAT, ScoreError, beat as fraction, canonical_json,
                          choice, fields, integer, name as valid_name, number, sequence)
from .io import read_json
from .motion_clock import BeatMap
from .recording import (MAX_RECORDING_VALUES, Recording, RecordingClock,
                        _write_json_document)
from .rigs import RigProfile, canonical_type_uri

CAPTURE_FORMAT = "dancerudiments.rig-capture"
QUATERNION_NORM_TOLERANCE = 1e-5


def _quaternion_groups(profile):
    groups = {}
    for index, channel in enumerate(profile.channels):
        if channel.interpolation == "quaternion":
            groups.setdefault((channel.bone, channel.data_path), {})[channel.array_index] = index
    if any(set(group) != {0, 1, 2, 3} for group in groups.values()):
        raise ScoreError("A quaternion rotation needs all four wxyz channels")
    return tuple(tuple(group[i] for i in range(4)) for group in groups.values())


def _unit_quaternion(values):
    norm = math.sqrt(math.fsum(value * value for value in values))
    if not math.isfinite(norm) or abs(norm - 1) > QUATERNION_NORM_TOLERANCE:
        raise ScoreError("Captured rotation_quaternion values must form a unit quaternion")
    return tuple(value / norm for value in values)


def _dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def _slerp(a, b, weight):
    a, b = _unit_quaternion(a), _unit_quaternion(b)
    cosine = _dot(a, b)
    if cosine < 0:
        b = tuple(-value for value in b)
        cosine = -cosine
    cosine = min(1.0, max(-1.0, cosine))
    if cosine > 0.9995:
        result = tuple((1 - weight) * x + weight * y for x, y in zip(a, b))
    else:
        angle = math.acos(cosine)
        divisor = math.sin(angle)
        left, right = math.sin((1 - weight) * angle) / divisor, math.sin(weight * angle) / divisor
        result = tuple(left * x + right * y for x, y in zip(a, b))
    # Normalizing also removes the small error of the near-parallel lerp branch.
    norm = math.sqrt(_dot(result, result))
    return tuple(value / norm for value in result)


@dataclass(frozen=True)
class RigCapture:
    """Timestamped physical controls in exactly the declared profile order.

    Values use the profile's units, *before* normalization to [-1, 1].  A capture
    preserves imported motion and provenance independently of musical tempo.
    Euler components retain their sampled winding; unwrap discontinuities in the
    source animation or use quaternion controls before capture.
    """

    profile: RigProfile
    frame_times_seconds: tuple[float, ...]
    frames: tuple[tuple[float, ...], ...]
    provenance_json: str = "{}"
    _times: tuple[Fraction, ...] = field(init=False, repr=False, compare=False)
    _quaternions: tuple[tuple[int, ...], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.profile, RigProfile):
            raise ScoreError("RigCapture requires a validated RigProfile")
        count = len(self.profile.channels)
        raw_times = sequence(self.frame_times_seconds, 1, MAX_RECORDING_VALUES // count,
                             "frame_times_seconds")
        times = tuple(number(time, "frame time") for time in raw_times)
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ScoreError("Capture frame times must strictly increase")
        raw_frames = sequence(self.frames, len(times), len(times), "frames")
        quaternions = _quaternion_groups(self.profile)
        frames = []
        for raw in raw_frames:
            row = tuple(number(value, "physical channel")
                        for value in sequence(raw, count, count, "frame"))
            self.profile.encode(row)  # validates physical ranges and discrete values
            for indices in quaternions:
                _unit_quaternion(tuple(row[i] for i in indices))
            frames.append(row)
        try:
            provenance = json.loads(self.provenance_json)
            if not isinstance(provenance, dict):
                raise ValueError("not an object")
        except (ValueError, TypeError, RecursionError) as exc:
            raise ScoreError("Capture provenance must be a finite JSON object") from exc
        object.__setattr__(self, "provenance_json", canonical_json(provenance))
        object.__setattr__(self, "frame_times_seconds", times)
        object.__setattr__(self, "frames", tuple(frames))
        object.__setattr__(self, "_times", tuple(Fraction(str(time)) for time in times))
        object.__setattr__(self, "_quaternions", quaternions)

    @property
    def provenance(self):
        return json.loads(self.provenance_json)

    @property
    def fingerprint(self):
        return hashlib.sha256(canonical_json(self.to_dict()).encode("ascii")).hexdigest()

    def to_dict(self):
        return dict(format=CAPTURE_FORMAT, schema_version=1, type_uri=self.profile.type_uri,
                    profile_sha256=self.profile.fingerprint, profile=self.profile.to_dict(),
                    frame_times_seconds=list(self.frame_times_seconds),
                    frames=[list(row) for row in self.frames], provenance=self.provenance)

    @classmethod
    def from_dict(cls, value):
        keys = {"format", "schema_version", "type_uri", "profile_sha256", "profile",
                "frame_times_seconds", "frames", "provenance"}
        fields(value, keys, keys, "rig capture")
        choice(value["format"], (CAPTURE_FORMAT,), "capture.format")
        integer(value["schema_version"], 1, 1, "capture.schema_version")
        profile = RigProfile.from_dict(value["profile"])
        if canonical_type_uri(value["type_uri"]) != profile.type_uri:
            raise ScoreError("Capture type does not match its profile")
        if value["profile_sha256"] != profile.fingerprint:
            raise ScoreError("Capture profile fingerprint mismatch")
        return cls(profile, value["frame_times_seconds"], value["frames"],
                   canonical_json(value["provenance"]))


def load_capture(path):
    return RigCapture.from_dict(read_json(path))


def write_capture(path, capture, *, overwrite=False):
    if not isinstance(capture, RigCapture):
        raise ScoreError("write_capture requires a validated RigCapture")
    _write_json_document(path, capture.to_dict(), overwrite=overwrite)


def _frame_at(capture, seconds):
    """Offline resampling, intentionally private rather than a playback API."""
    if not capture._times[0] <= seconds <= capture._times[-1]:
        raise ScoreError("Requested source time lies outside the captured motion")
    index = min(bisect_right(capture._times, seconds) - 1, len(capture._times) - 1)
    if index == len(capture._times) - 1 or seconds == capture._times[index]:
        values = list(capture.frames[index])
        for indices in capture._quaternions:
            for i, value in zip(indices, _unit_quaternion(tuple(values[i] for i in indices))):
                values[i] = value
        return values
    weight = float((seconds - capture._times[index]) /
                   (capture._times[index + 1] - capture._times[index]))
    left, right = capture.frames[index], capture.frames[index + 1]
    values = [a if channel.interpolation == "step" else (1 - weight) * a + weight * b
              for a, b, channel in zip(left, right, capture.profile.channels)]
    for indices in capture._quaternions:
        rotation = _slerp(tuple(left[i] for i in indices), tuple(right[i] for i in indices), weight)
        for i, value in zip(indices, rotation):
            values[i] = value
    return values


def compile_capture(capture, *, name, source_beat_map, clock, sample_count,
                    source_beat_offset=0, motion_rate=1):
    """Resample a capture into a typed native-playable rig motion.

    ``source_beat = source_beat_offset + motion_rate * (absolute_pip / 64)``

    The source beat map then supplies the corresponding capture time.  Rate 0.5
    consumes half a source beat per output beat; 2 consumes two.  ``clock`` is the
    recording's nominal presentation tempo/origin, and ``start_pip`` is an
    absolute musical position.  A live target BeatMap can later change playback
    tempo without recompiling.  There is no implicit loop, clamp, tempo estimate,
    retargeting, endpoint extension or foot-contact correction.
    """
    from .motion import RigMotion

    if not isinstance(capture, RigCapture):
        raise ScoreError("compile_capture requires a validated RigCapture")
    if not isinstance(source_beat_map, BeatMap):
        raise ScoreError("An explicit source BeatMap is required")
    if not isinstance(clock, RecordingClock):
        raise ScoreError("A RecordingClock with BPM provenance is required")
    valid_name(name)
    integer(sample_count, 1, MAX_RECORDING_VALUES // len(capture.profile.channels), "sample_count")
    if clock.start_pip + sample_count > 2147483647:
        raise ScoreError("Recording exceeds the signed int32 pip range")
    offset = fraction(source_beat_offset, "source_beat_offset")
    rate = fraction(motion_rate, "motion_rate")
    if rate <= 0:
        raise ScoreError("motion_rate must be positive")

    def time_for(pip):
        return source_beat_map.seconds_fraction(offset + rate * Fraction(pip, PIPS_PER_BEAT))

    # Check both extents before allocating/resampling. All maps and rates are
    # monotonic, so no intermediate requested time can escape these bounds.
    first, last = time_for(clock.start_pip), time_for(clock.start_pip + sample_count - 1)
    if first < capture._times[0] or last > capture._times[-1]:
        raise ScoreError("Requested beat range exceeds the captured motion; choose an explicit excerpt")
    rows = []
    previous = {}
    for pip in range(clock.start_pip, clock.start_pip + sample_count):
        values = _frame_at(capture, time_for(pip))
        # q and -q describe the same orientation. Keep adjacent compiled samples
        # on the same hemisphere even when input files alternate their signs.
        for indices in capture._quaternions:
            rotation = tuple(values[i] for i in indices)
            if indices in previous and _dot(previous[indices], rotation) < 0:
                rotation = tuple(-value for value in rotation)
                for i, value in zip(indices, rotation):
                    values[i] = value
            previous[indices] = rotation
        rows.append(capture.profile.encode(values))
    provenance = dict(producer="dancerudiments.rig-capture-compiler",
                      source_capture_sha256=capture.fingerprint,
                      source_profile_sha256=capture.profile.fingerprint,
                      source_provenance=capture.provenance,
                      source_beat_map=source_beat_map.to_dict(),
                      source_beat_offset=str(offset), motion_rate=str(rate),
                      source_time_range_seconds=[float(first), float(last)],
                      interpolation="linear scalars; shortest-path quaternion SLERP; held discrete controls",
                      loop_policy="non_looping")
    recording = Recording(name, capture.profile.dimensions, tuple(rows), clock, canonical_json(provenance))
    return RigMotion(recording=recording, profile=capture.profile)
