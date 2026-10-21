"""Typed rig motion over the existing native N-dimensional recording sampler.

Python validates the binding and converts channel units. All live sampling is
performed by C++ SampledRecording; no second Python movement engine is present.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from ._validation import ScoreError, canonical_json, fields, integer
from .io import read_json
from .recording import Recording, _write_json_document
from .rigs import RigProfile, canonical_type_uri

FORMAT = 'dancerudiments.rig-motion'


@dataclass(frozen=True)
class RigMotion:
    """A non-looping pip recording bound to one exact, versioned rig profile."""

    recording: Recording
    profile: RigProfile

    def __post_init__(self):
        if not isinstance(self.recording, Recording) or not isinstance(self.profile, RigProfile):
            raise ScoreError('RigMotion requires a Recording and RigProfile')
        if self.recording.dimensions != self.profile.dimensions:
            raise ScoreError('Recording columns must exactly match the rig profile channel order')
        # A legal normalized scalar row can still contain a non-integral switch
        # or an invalid quaternion. Validate physical channel semantics as well.
        for row in self.recording.samples:
            self.profile.decode(row)

    @property
    def type_uri(self):
        return self.profile.type_uri

    @property
    def name(self):
        return self.recording.name

    @property
    def fingerprint(self):
        return hashlib.sha256(canonical_json(self.to_dict()).encode('ascii')).hexdigest()

    def to_dict(self):
        return dict(format=FORMAT, schema_version=1, type_uri=self.type_uri,
                    profile_sha256=self.profile.fingerprint,
                    profile=self.profile.to_dict(), recording=self.recording.to_dict())

    @classmethod
    def from_dict(cls, data):
        keys = {'format', 'schema_version', 'type_uri', 'profile_sha256', 'profile', 'recording'}
        fields(data, keys, keys, 'rig motion')
        if data['format'] != FORMAT:
            raise ScoreError('Expected dancerudiments.rig-motion')
        integer(data['schema_version'], 1, 1, 'schema_version')
        profile = RigProfile.from_dict(data['profile'])
        if canonical_type_uri(data['type_uri']) != profile.type_uri:
            raise ScoreError('Motion type does not match the rig profile type')
        if data['profile_sha256'] != profile.fingerprint:
            raise ScoreError('Rig profile fingerprint mismatch')
        return cls(Recording.from_dict(data['recording']), profile)

    def require_profile(self, target):
        """Refuse an incompatible skeleton, rest basis, units or channel mapping."""
        if not isinstance(target, RigProfile) or target.fingerprint != self.profile.fingerprint:
            raise ScoreError('Target rig profile differs; retarget and recapture for that rig')

    def to_native(self):
        return self.recording.to_native()

    def player(self):
        return RigMotionPlayer(self)


class RigMotionPlayer:
    """Native pip playback with explicit physical-channel decoding.

    Out-of-range pips raise. Seek, pause and tempo changes are supplied by the
    caller's audio/beat clock rather than a separately accumulated motion timer.
    """

    def __init__(self, motion):
        if not isinstance(motion, RigMotion):
            raise ScoreError('A validated RigMotion is required')
        self._profile = motion.profile
        self._native = motion.to_native()

    @property
    def profile(self):
        return self._profile

    @property
    def start_pip(self):
        return self._native.start_pip

    @property
    def sample_count(self):
        return self._native.sample_count

    def sample(self, pip):
        integer(pip, -2147483648, 2147483647, 'pip')
        return self.profile.decode(self._native.sample(pip))

    def by_channel(self, pip):
        return {channel.number: value for channel, value in zip(self.profile.channels, self.sample(pip))}

    def sample_time(self, seconds, target_beat_map):
        from .motion_clock import BeatMap
        if not isinstance(target_beat_map, BeatMap):
            raise ScoreError('An explicit target BeatMap is required for timed playback')
        return self.sample(target_beat_map.pip_at(seconds))


def load_rig_motion(path):
    return RigMotion.from_dict(read_json(path))


def write_rig_motion(path, motion, *, overwrite=False):
    if not isinstance(motion, RigMotion):
        raise ScoreError('write_rig_motion requires a validated RigMotion')
    _write_json_document(path, motion.to_dict(), overwrite=overwrite)
