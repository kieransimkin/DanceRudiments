"""Bounded BVH authoring with optional NumPy, without Blender or live sampling.

BVH offsets define joint frames, not oriented Blender bones.  The portable
source carrier therefore uses identity rest rotations at accumulated joint
offsets.  Its displayed bone lengths do not change the recorded joint frames.
Declared intrinsic Euler rotations become local wxyz quaternions. Positional
channels default to additive local translations. An explicit Blender-compatible
absolute-local convention is available for files whose positions include their
rest offsets; the selected convention is part of the stable source profile.

No Blender implementation is copied here.  Format reference:
https://research.cs.wisc.edu/graphics/Courses/cs-838-1999/Jeff/BVH.html
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import re

from ._validation import ScoreError, beat, canonical_json, integer, name as valid_name, number
from .recording import MAX_RECORDING_VALUES, RecordingClock
from .rigs import RigChannel, RigProfile, channel_name

SOURCE_ADAPTER = 'dancerudiments.skeletal-source-v1'
DEFAULT_CHUNK_VALUES = 500_000
_NUM = rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?'
_NUMERIC_ROW = re.compile(rb'\s*' + _NUM + rb'(?:\s+' + _NUM + rb')*\s*\Z')
_CHANNELS = frozenset(axis + kind for axis in 'XYZ' for kind in ('position', 'rotation'))
_NEUTRAL = {'location': (0., 0., 0.), 'rotation_quaternion': (1., 0., 0., 0.),
            'scale': (1., 1., 1.)}


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError('BVH authoring requires the optional NumPy dependency') from exc
    return np


def _positive(value, label):
    result = number(value, label)
    if result <= 0:
        raise ScoreError(f'{label} must be positive')
    return result


@dataclass(frozen=True)
class BVHLimits:
    """Per-file resource bounds, checked before allocating motion matrices."""

    max_file_bytes: int = 256 * 1024 * 1024
    max_header_bytes: int = 4 * 1024 * 1024
    max_line_bytes: int = 1024 * 1024
    max_joints: int = 1024
    max_depth: int = 128
    max_channels: int = 6144
    max_frames: int = 2_000_000
    max_values: int = MAX_RECORDING_VALUES

    def __post_init__(self):
        for key, value in vars(self).items():
            integer(value, 1, 2_147_483_647, key)
        if self.max_depth > 256:
            raise ScoreError('max_depth must not exceed 256')


@dataclass(frozen=True)
class BVHJoint:
    name: str
    parent: int | None
    offset: tuple[float, float, float]
    channels: tuple[str, ...]
    channel_start: int
    end_sites: tuple[tuple[float, float, float], ...] = ()


class _Reader:
    def __init__(self, stream, limits):
        self.stream, self.limits = stream, limits
        self.byte_count = 0
        self.digest = hashlib.sha256()

    def line(self):
        raw = self.stream.readline(self.limits.max_line_bytes + 1)
        if len(raw) > self.limits.max_line_bytes:
            raise ScoreError('BVH line exceeds max_line_bytes')
        self.byte_count += len(raw)
        if self.byte_count > self.limits.max_file_bytes:
            raise ScoreError('BVH exceeds max_file_bytes')
        self.digest.update(raw)
        return raw

    def nonempty(self):
        while True:
            raw = self.line()
            if not raw or raw.strip():
                return raw


class _Hierarchy:
    def __init__(self, text, limits):
        self.tokens = re.findall(r'[{}]|[^\s{}]+', text)
        if any(len(token) > 128 for token in self.tokens):
            raise ScoreError('BVH hierarchy token is too long')
        self.index, self.limits = 0, limits
        self.joints, self.names, self.channel_count = [], set(), 0

    def take(self, expected=None):
        if self.index >= len(self.tokens):
            raise ScoreError('Unexpected end of BVH hierarchy')
        value = self.tokens[self.index]
        self.index += 1
        if expected is not None and value != expected:
            raise ScoreError(f'Expected BVH {expected!r}, got {value!r}')
        return value

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def offset(self):
        self.take('OFFSET')
        values = []
        for _ in range(3):
            token = self.take()
            if not re.fullmatch(_NUM, token.encode('utf-8')):
                raise ScoreError('Invalid BVH OFFSET number')
            values.append(number(float(token), 'BVH offset'))
        return tuple(values)

    def joint(self, parent, depth):
        if depth > self.limits.max_depth or len(self.joints) >= self.limits.max_joints:
            raise ScoreError('BVH hierarchy exceeds joint/depth limits')
        self.take('ROOT' if parent is None else 'JOINT')
        joint_name = self.take()
        if (joint_name in self.names or joint_name in ('{', '}') or
                len(joint_name.encode('utf-8')) > 63 or any(ord(c) < 32 for c in joint_name)):
            raise ScoreError('BVH joint names must be unique and fit Blender\'s 63-byte bone names')
        self.names.add(joint_name)
        self.take('{')
        offset = self.offset()
        self.take('CHANNELS')
        count_token = self.take()
        if not count_token.isdecimal() or len(count_token) > 2:
            raise ScoreError('Invalid BVH channel count')
        count = int(count_token)
        if not 0 <= count <= 6:
            raise ScoreError('BVH supports at most XYZ translation and rotation channels per joint')
        channels = tuple(self.take() for _ in range(count))
        if len(set(channels)) != len(channels) or any(c not in _CHANNELS for c in channels):
            raise ScoreError('Unknown or duplicate BVH channels')
        first = self.channel_count
        self.channel_count += count
        if self.channel_count > self.limits.max_channels:
            raise ScoreError('BVH exceeds max_channels')
        index = len(self.joints)
        self.joints.append(None)
        end_sites = []
        while self.peek() != '}':
            if self.peek() == 'JOINT':
                self.joint(index, depth + 1)
            elif self.peek() == 'End':
                if end_sites:
                    raise ScoreError('Repeated BVH End Site')
                self.take('End')
                self.take('Site')
                self.take('{')
                end_sites.append(self.offset())
                self.take('}')
            else:
                raise ScoreError('Expected BVH JOINT, End Site or closing brace')
        self.take('}')
        self.joints[index] = BVHJoint(joint_name, parent, offset, channels, first, tuple(end_sites))

    def parse(self):
        self.take('HIERARCHY')
        while self.peek() == 'ROOT':
            self.joint(None, 1)
        if self.peek() is not None or not self.joints or not self.channel_count:
            raise ScoreError('Expected a BVH hierarchy with at least one motion channel')
        return tuple(self.joints), self.channel_count


def _axis_matrix(axis_forward, axis_up):
    """Map explicit right-handed source axes to Blender +Y forward, +Z up."""
    np = _numpy()
    def vector(label):
        if label not in ('X', 'Y', 'Z', '-X', '-Y', '-Z'):
            raise ScoreError('Axes must be X, Y, Z, -X, -Y or -Z')
        result = np.zeros(3, dtype=np.float64)
        result['XYZ'.index(label[-1])] = -1. if label.startswith('-') else 1.
        return result
    forward, up = vector(axis_forward), vector(axis_up)
    if axis_forward[-1] == axis_up[-1]:
        raise ScoreError('Forward and up axes must be perpendicular')
    return np.stack((np.cross(forward, up), forward, up))


def _multiply_quaternions(a, b):
    np = _numpy()
    result = np.empty_like(a)
    result[:, 0] = a[:, 0] * b[:, 0] - np.sum(a[:, 1:] * b[:, 1:], axis=1)
    result[:, 1:] = (a[:, :1] * b[:, 1:] + b[:, :1] * a[:, 1:] +
                     np.cross(a[:, 1:], b[:, 1:]))
    return result


def _continuous_quaternions(quaternions):
    np = _numpy()
    if len(quaternions) > 1:
        dots = np.sum(quaternions[:-1] * quaternions[1:], axis=1)
        signs = np.cumprod(np.where(dots < 0., -1., 1.))
        quaternions[1:] *= signs[:, None]
    return quaternions


def _profile_and_frames(joints, raw, *, source_id, unit_scale, axis_forward, axis_up,
                        location_range, translation_convention, root_offset_policy, limits):
    np = _numpy()
    if not isinstance(source_id, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,79}', source_id):
        raise ScoreError('source_id must be a lowercase identifier of at most 80 characters')
    unit_scale, location_range = _positive(unit_scale, 'unit_scale'), _positive(location_range, 'location_range')
    if translation_convention not in ('offset-plus-channel', 'blender-absolute'):
        raise ScoreError('translation_convention must be offset-plus-channel or blender-absolute')
    if root_offset_policy not in ('retain', 'motion'):
        raise ScoreError('root_offset_policy must be retain or motion')
    axis = _axis_matrix(axis_forward, axis_up)
    channels, omitted, skeleton, definitions = [], [], [], []
    heads = []
    groups = []
    for index, joint in enumerate(joints):
        rest_offset = (0., 0., 0.) if root_offset_policy == 'motion' and joint.parent is None else joint.offset
        offset = axis @ np.asarray(rest_offset) * unit_scale
        head = offset + (heads[joint.parent] if joint.parent is not None else 0.)
        if not np.isfinite(head).all():
            raise ScoreError('Converted BVH rest offsets are not finite')
        heads.append(head)
        offsets = [child.offset for child in joints if child.parent == index] or list(joint.end_sites)
        length = next((float(np.linalg.norm(o)) * unit_scale for o in offsets if any(o)), 0.1)
        if not math.isfinite(length):
            raise ScoreError('BVH bone length is not finite')
        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, 3] = head
        skeleton.append(dict(name=joint.name, parent=joints[joint.parent].name if joint.parent is not None else None,
                             rest_matrix=matrix.ravel().tolist(), length=max(length, 0.0001), use_deform=True))
        definitions.append(dict(name=joint.name, parent=skeleton[-1]['parent'], offset=list(rest_offset),
                                channels=list(joint.channels), end_sites=[list(o) for o in joint.end_sites]))
        position_present = any(c.endswith('position') for c in joint.channels)
        if root_offset_policy == 'motion' and joint.parent is None:
            position_present = True
        for path, present in (('location', position_present),
                              ('rotation_quaternion', any(c.endswith('rotation') for c in joint.channels)),
                              ('scale', False)):
            defaults = _NEUTRAL[path]
            if not present:
                omitted.append(dict(bone=joint.name, data_path=path, values=list(defaults)))
                continue
            start = len(channels)
            bound = location_range if path == 'location' else 1.
            for component, default in enumerate(defaults):
                number_ = len(channels) + 1
                channels.append(RigChannel(number_, channel_name(number_, joint.name, path, component),
                    joint.name, path, component, 'blender_unit' if path == 'location' else 'unitless',
                    -bound, bound, default,
                    interpolation='quaternion' if path == 'rotation_quaternion' else 'linear',
                    rotation_mode='QUATERNION' if path == 'rotation_quaternion' else ''))
            groups.append((joint, path, start, len(defaults)))
    if len(raw) * len(channels) > limits.max_values:
        raise ScoreError('Decoded BVH exceeds max_values; increase the explicit per-file limit')
    frames = np.empty((len(raw), len(channels)), dtype=np.float64)
    for joint, path, first, width in groups:
        if path == 'location':
            position = np.zeros((len(raw), 3), dtype=np.float64)
            for index, channel in enumerate(joint.channels):
                if channel.endswith('position'):
                    position[:, 'XYZ'.index(channel[0])] = raw[:, joint.channel_start + index]
            has_position = any(c.endswith('position') for c in joint.channels)
            if translation_convention == 'blender-absolute' and has_position:
                position -= np.asarray(joint.offset)
            if root_offset_policy == 'motion' and joint.parent is None:
                # Changing the root's rest origin changes every descendant's
                # rest world position equally. The offset becomes local root
                # translation, preserving every posed joint in world space.
                position += np.asarray(joint.offset)
            position = (position @ axis.T) * unit_scale
            if not np.isfinite(position).all() or np.any(np.abs(position) > location_range):
                raise ScoreError('BVH translation exceeds fixed location_range; supply a suitable source-level bound')
            frames[:, first:first + width] = position
        else:
            rotation = np.zeros((len(raw), 4), dtype=np.float64)
            rotation[:, 0] = 1.
            for index, channel in enumerate(joint.channels):
                if not channel.endswith('rotation'):
                    continue
                angle = np.deg2rad(np.remainder(raw[:, joint.channel_start + index], 360.)) * 0.5
                component = np.zeros_like(rotation)
                component[:, 0] = np.cos(angle)
                component[:, 1 + 'XYZ'.index(channel[0])] = np.sin(angle)
                rotation = _multiply_quaternions(rotation, component)
            # Proper axis changes conjugate a quaternion by rotating its vector part.
            rotation[:, 1:] = rotation[:, 1:] @ axis.T
            rotation /= np.linalg.norm(rotation, axis=1)[:, None]
            frames[:, first:first + width] = _continuous_quaternions(rotation)
    digest = hashlib.sha256(canonical_json(skeleton).encode('ascii')).hexdigest()[:16]
    source = dict(adapter=SOURCE_ADAPTER, scene_unit_scale_length=1.,
        coordinate_system='Blender right-handed +Z up, +Y forward; identity joint rest rotations',
        skeleton=skeleton, object_motion_root=next(j.name for j in joints if j.parent is None),
        omitted_neutral_groups=omitted, neutral_tolerance=0.,
        carrier_inheritance='FULL; local location; inherit rotation',
        transform_bounds=dict(location_range=location_range, scale_range=1.),
        bvh=dict(joints=definitions, source_axis_forward=axis_forward, source_axis_up=axis_up,
                 source_to_blender=axis.ravel().tolist(), source_unit_to_blender_unit=unit_scale,
                 unit_policy=('source-units-unverified' if unit_scale == 1. else
                              'explicit-caller-scale; physical units unverified'),
                 unit_note='BVH does not declare physical units; Blender units are not asserted to be metres',
                 translation_convention=translation_convention,
                 root_offset_policy=root_offset_policy,
                 root_offset_note=('Original root offsets are retained in clip provenance; only root rest origins '
                                   'move to motion channels, with all child offsets unchanged' if root_offset_policy == 'motion'
                                   else 'Original root offsets remain in the source rest skeleton'),
                 rotation_convention='intrinsic rotations in declared channel order; degrees',
                 bone_display='identity rest rotations; lengths do not alter joint offsets'))
    profile = RigProfile(f'syn://type/danceflow/motion/skeletal/source/{source_id}/skeleton_{digest}',
                         source_id, tuple(channels), source_json=canonical_json(source))
    frames.setflags(write=False)
    return profile, frames


@dataclass(frozen=True)
class BVHClip:
    """All source frames, with both original BVH channels and physical controls."""

    profile: RigProfile
    joints: tuple[BVHJoint, ...]
    source_frames: object
    frames: object
    frame_time_seconds: Fraction
    source_sha256: str
    metadata_json: str

    def __post_init__(self):
        np = _numpy()
        if (not isinstance(self.profile, RigProfile) or not isinstance(self.joints, tuple)
                or not self.joints or any(not isinstance(j, BVHJoint) for j in self.joints)):
            raise ScoreError('BVHClip needs a validated profile and joint hierarchy')
        if (not isinstance(self.frame_time_seconds, Fraction) or self.frame_time_seconds <= 0
                or not math.isfinite(float(self.frame_time_seconds))
                or not math.isfinite(float(1 / self.frame_time_seconds))):
            raise ScoreError('BVHClip needs a positive representable frame interval')
        if not isinstance(self.source_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', self.source_sha256):
            raise ScoreError('BVHClip source_sha256 must identify its original bytes')
        try:
            metadata = json.loads(self.metadata_json)
            if not isinstance(metadata, dict):
                raise ValueError('not an object')
            object.__setattr__(self, 'metadata_json', canonical_json(metadata))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ScoreError('BVHClip metadata must be a finite JSON object') from exc
        rows = self.frames
        source = self.source_frames
        if (not isinstance(rows, np.ndarray) or rows.dtype != np.float64 or rows.ndim != 2
                or rows.shape[1] != len(self.profile.channels) or len(rows) < 1
                or not isinstance(source, np.ndarray) or source.dtype != np.float64
                or source.shape != (len(rows), sum(len(j.channels) for j in self.joints))):
            raise ScoreError('BVHClip arrays do not match its hierarchy and profile')
        if not np.isfinite(rows).all() or not np.isfinite(source).all():
            raise ScoreError('BVHClip arrays must be finite')
        minimum = np.asarray([c.minimum for c in self.profile.channels])
        maximum = np.asarray([c.maximum for c in self.profile.channels])
        if np.any(rows < minimum) or np.any(rows > maximum):
            raise ScoreError('BVHClip controls exceed profile bounds')
        for indices in _quaternion_groups(self.profile):
            if np.any(np.abs(np.linalg.norm(rows[:, indices], axis=1) - 1.) > 1e-5):
                raise ScoreError('BVHClip has a non-unit quaternion')
        rows.setflags(write=False)
        source.setflags(write=False)

    @property
    def frame_count(self):
        return len(self.frames)

    @property
    def duration_fraction(self):
        return (self.frame_count - 1) * self.frame_time_seconds

    @property
    def duration_seconds(self):
        return float(self.duration_fraction)

    @property
    def source_fps(self):
        return float(1 / self.frame_time_seconds)

    @property
    def metadata(self):
        return json.loads(self.metadata_json)


def override_bvh_frame_time(clip, *, frame_time_seconds, evidence):
    """Apply one explicitly evidenced timing correction, preserving source data.

    Some third-party conversions replace every original frame-rate header with
    a common value. Only the caller can supply the correction and its evidence;
    this function never infers timing from motion values or a filename. Original
    bytes, pose arrays and the stable source profile remain unchanged. Metadata
    records both the original declared interval and the effective interval.
    """
    if not isinstance(clip, BVHClip):
        raise ScoreError('A frame-time override requires BVHClip')
    if not isinstance(frame_time_seconds, (str, Fraction)):
        raise ScoreError('frame_time_seconds must be an explicit rational string or Fraction')
    interval = beat(frame_time_seconds, 'frame_time_seconds')
    if interval <= 0:
        raise ScoreError('frame_time_seconds must be positive')
    if not isinstance(evidence, dict) or not evidence:
        raise ScoreError('A frame-time override requires nonempty JSON evidence')
    evidence = json.loads(canonical_json(evidence))
    metadata = clip.metadata
    if 'frame_time_override' in metadata:
        raise ScoreError('This clip already has a frame-time override; return to its original source')
    original = dict(frame_time_fraction=str(clip.frame_time_seconds), fps=clip.source_fps,
                    duration_seconds=clip.duration_seconds)
    metadata.update(source_fps=float(1 / interval), source_frame_time_fraction=str(interval),
                    source_duration_seconds=float((clip.frame_count - 1) * interval),
                    frame_time_override=dict(frame_time_seconds=str(interval), evidence=evidence,
                                             original_header=original))
    return replace(clip, frame_time_seconds=interval, metadata_json=canonical_json(metadata))


def _read_bvh(stream, *, source_id, unit_scale, axis_forward, axis_up, location_range,
              translation_convention, root_offset_policy, limits, source_name):
    np = _numpy()
    if not isinstance(limits, BVHLimits):
        raise ScoreError('limits must be BVHLimits')
    reader, header = _Reader(stream, limits), []
    while True:
        raw = reader.line()
        if not raw:
            raise ScoreError('BVH is missing MOTION')
        if raw.strip() == b'MOTION':
            break
        if reader.byte_count > limits.max_header_bytes:
            raise ScoreError('BVH hierarchy exceeds max_header_bytes')
        header.append(raw)
    try:
        text = b''.join(header).decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ScoreError('BVH hierarchy must be UTF-8 text') from exc
    joints, channel_count = _Hierarchy(text, limits).parse()
    frames_match = re.fullmatch(rb'\s*Frames\s*:\s*([0-9]{1,10})\s*', reader.nonempty())
    if not frames_match:
        raise ScoreError('Expected BVH Frames: count')
    frame_count = int(frames_match.group(1))
    integer(frame_count, 1, limits.max_frames, 'BVH frame count')
    if frame_count * channel_count > limits.max_values:
        raise ScoreError('BVH source matrix exceeds max_values')
    time_match = re.fullmatch(rb'\s*Frame\s+Time\s*:\s*(' + _NUM + rb')\s*', reader.nonempty())
    if not time_match or len(time_match.group(1)) > 64:
        raise ScoreError('Expected a finite positive BVH Frame Time')
    token = time_match.group(1).decode('ascii')
    dt = _positive(float(token), 'BVH Frame Time')
    if not math.isfinite(1. / dt):
        raise ScoreError('BVH frame rate is not representable')
    frame_time = Fraction(token)
    source_frames = np.empty((frame_count, channel_count), dtype=np.float64)
    for frame in range(frame_count):
        line = reader.nonempty()
        if not line or not _NUMERIC_ROW.fullmatch(line):
            raise ScoreError(f'BVH frame {frame} is missing or contains invalid numbers')
        row = np.fromstring(line, dtype=np.float64, sep=' ')
        if row.size != channel_count or not np.isfinite(row).all():
            raise ScoreError(f'BVH frame {frame} has wrong channel count or non-finite values')
        source_frames[frame] = row
    if reader.nonempty():
        raise ScoreError('BVH has data after its declared frame count')
    profile, frames = _profile_and_frames(joints, source_frames, source_id=source_id,
        unit_scale=unit_scale, axis_forward=axis_forward, axis_up=axis_up,
        location_range=location_range, translation_convention=translation_convention,
        root_offset_policy=root_offset_policy, limits=limits)
    source_frames.setflags(write=False)
    metadata = dict(producer='dancerudiments.bvh-import-v1', source_kind='skeletal_bvh',
        source_name=str(source_name), source_sha256=reader.digest.hexdigest(), source_bytes=reader.byte_count,
        source_frame_count=frame_count, source_fps=float(1 / frame_time),
        source_frame_time_fraction=str(frame_time), source_duration_seconds=float((frame_count - 1) * frame_time),
        original_channel_count=channel_count, original_joint_count=len(joints),
        original_root_offsets={j.name: list(j.offset) for j in joints if j.parent is None},
        root_offset_policy=root_offset_policy,
        time_origin='first BVH sample is 0 seconds',
        retargeting='none; source skeleton carrier, not Rigify controls')
    return BVHClip(profile, joints, source_frames, frames, frame_time, reader.digest.hexdigest(),
                   canonical_json(metadata))


def load_bvh(path, *, source_id, unit_scale=1., axis_forward='-Z', axis_up='Y',
             location_range=10000., translation_convention='offset-plus-channel',
             root_offset_policy='retain', limits=None):
    """Read a local BVH with explicit units/axes and positional interpretation.

    ``offset-plus-channel`` follows the published BVH root offset convention;
    ``blender-absolute`` matches Blender's importer for positional channels
    containing absolute local positions, including non-root joints. The choice
    is never guessed from a clip. No downloads or skeleton retargeting occur.
    Opt-in ``root_offset_policy='motion'`` moves only root rest offsets into
    root translation channels. It preserves world poses and child proportions,
    and retains the original offsets in clip provenance for reconstruction.
    """
    limits = BVHLimits() if limits is None else limits
    if not isinstance(limits, BVHLimits):
        raise ScoreError('limits must be BVHLimits')
    path = Path(path)
    if path.stat().st_size > limits.max_file_bytes:
        raise ScoreError('BVH exceeds max_file_bytes')
    with path.open('rb') as stream:
        return _read_bvh(stream, source_id=source_id, unit_scale=unit_scale,
            axis_forward=axis_forward, axis_up=axis_up, location_range=location_range,
            translation_convention=translation_convention, root_offset_policy=root_offset_policy,
            limits=limits, source_name=path.name)


def parse_bvh(text, *, source_id, unit_scale=1., axis_forward='-Z', axis_up='Y',
              location_range=10000., translation_convention='offset-plus-channel',
              root_offset_policy='retain', limits=None, source_name='<memory>'):
    """Parse caller-owned text/bytes, useful for synthetic fixtures and adapters."""
    limits = BVHLimits() if limits is None else limits
    if not isinstance(limits, BVHLimits):
        raise ScoreError('limits must be BVHLimits')
    if not isinstance(text, (str, bytes)):
        raise ScoreError('BVH input must be text or bytes')
    if len(text) > limits.max_file_bytes:
        raise ScoreError('BVH exceeds max_file_bytes')
    payload = text.encode('utf-8') if isinstance(text, str) else text
    if len(payload) > limits.max_file_bytes:
        raise ScoreError('BVH exceeds max_file_bytes')
    return _read_bvh(io.BytesIO(payload), source_id=source_id, unit_scale=unit_scale,
        axis_forward=axis_forward, axis_up=axis_up, location_range=location_range,
        translation_convention=translation_convention, root_offset_policy=root_offset_policy,
        limits=limits, source_name=source_name)


def _quaternion_groups(profile):
    groups = {}
    for index, channel in enumerate(profile.channels):
        if channel.interpolation == 'quaternion':
            groups.setdefault(channel.bone, {})[channel.array_index] = index
    return tuple(tuple(group[i] for i in range(4)) for group in groups.values())


@dataclass(frozen=True)
class BVHMotionChunk:
    """Validated bounded compiled arrays; compatible with standard rig-motion JSON.

    ``to_recording_dict`` avoids constructing hundreds of thousands of Python
    scalar validators twice. ``to_rig_motion`` remains available for canonical
    object consumers. All live playback still uses native SampledRecording.
    """

    name: str
    profile: RigProfile
    samples: object
    clock: RecordingClock
    metadata_json: str = '{}'

    def __post_init__(self):
        np = _numpy()
        try:
            metadata = json.loads(self.metadata_json)
            if not isinstance(metadata, dict):
                raise ValueError('not an object')
            object.__setattr__(self, 'metadata_json', canonical_json(metadata))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ScoreError('BVH chunk metadata must be a finite JSON object') from exc
        try:
            array = np.array(self.samples, dtype=np.float64, order='C', copy=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ScoreError('BVH chunk samples must be a rectangular float64 matrix') from exc
        array.setflags(write=False)
        object.__setattr__(self, 'samples', array)
        self.validate()

    @property
    def metadata(self):
        return json.loads(self.metadata_json)

    def validate(self):
        np = _numpy()
        valid_name(self.name)
        if not isinstance(self.profile, RigProfile) or not isinstance(self.clock, RecordingClock):
            raise ScoreError('BVH chunk needs a validated RigProfile and RecordingClock')
        rows = self.samples
        if (rows.dtype != np.float64 or rows.ndim != 2 or rows.shape[1] != len(self.profile.channels)
                or not 1 <= rows.size <= MAX_RECORDING_VALUES):
            raise ScoreError('BVH chunk dimensions or scalar budget invalid')
        if self.clock.start_pip + len(rows) > 2147483647:
            raise ScoreError('BVH chunk exceeds signed int32 pip range')
        if not np.isfinite(rows).all() or np.any(np.abs(rows) > 1.):
            raise ScoreError('BVH chunk samples must be finite and normalized to [-1,1]')
        if not np.array_equal(rows, np.round(rows, 12)):
            raise ScoreError('BVH chunk samples must be rounded to 12 decimal places')
        for indices in _quaternion_groups(self.profile):
            if np.any(np.abs(np.linalg.norm(rows[:, indices], axis=1) - 1.) > 1e-5):
                raise ScoreError('BVH chunk contains non-unit quaternions')
        for index, channel in enumerate(self.profile.channels):
            if channel.value_type != 'float':
                physical = channel.minimum + (rows[:, index] + 1.) * .5 * (channel.maximum - channel.minimum)
                tolerance = max(1e-9, (channel.maximum - channel.minimum) * 1e-12)
                if np.any(np.abs(physical - np.rint(physical)) > tolerance):
                    raise ScoreError('BVH chunk has non-integral discrete channels')
                if channel.enum_items and not np.isin(np.rint(physical), [x[0] for x in channel.enum_items]).all():
                    raise ScoreError('BVH chunk has an undeclared discrete value')

    def to_recording_dict(self):
        from dataclasses import asdict
        return dict(format='dancerudiments.recording', schema_version=1, pips_per_beat=64,
            sample_dtype='float64', sample_decimals=12, name=self.name,
            dimensions=list(self.profile.dimensions), samples=self.samples.tolist(),
            clock=asdict(self.clock), provenance=self.metadata)

    def to_dict(self):
        return dict(format='dancerudiments.rig-motion', schema_version=1,
            type_uri=self.profile.type_uri, profile_sha256=self.profile.fingerprint,
            profile=self.profile.to_dict(), recording=self.to_recording_dict())

    def to_rig_motion(self):
        from .motion import RigMotion
        from .recording import Recording
        return RigMotion(Recording.from_dict(self.to_recording_dict()), self.profile)


def _resample(clip, positions):
    """Vectorized offline interpolation of known source-frame coordinates."""
    np = _numpy()
    left_index = np.floor(positions).astype(np.int64)
    right_index = np.minimum(left_index + 1, clip.frame_count - 1)
    weight = (positions - left_index)[:, None]
    left, right = clip.frames[left_index], clip.frames[right_index]
    result = left + weight * (right - left)
    for indices in _quaternion_groups(clip.profile):
        a, b = left[:, indices], right[:, indices]
        dot = np.sum(a * b, axis=1)
        b = b * np.where(dot < 0., -1., 1.)[:, None]
        dot = np.clip(np.abs(dot), 0., 1.)
        angle = np.arccos(dot)
        sine = np.sin(angle)
        small = dot > .9995
        safe = np.where(small, 1., sine)
        alpha = np.sin((1. - weight[:, 0]) * angle) / safe
        beta = np.sin(weight[:, 0] * angle) / safe
        alpha[small], beta[small] = 1. - weight[small, 0], weight[small, 0]
        rotation = alpha[:, None] * a + beta[:, None] * b
        rotation /= np.linalg.norm(rotation, axis=1)[:, None]
        result[:, indices] = rotation
    return result


def compile_bvh(clip, *, name, source_bpm=None, source_beat_zero_seconds=None,
                max_chunk_values=DEFAULT_CHUNK_VALUES):
    """Yield contiguous complete-action pip chunks, without invented music timing.

    The default 60 BPM is explicitly a time-only coordinate (one beat = one
    second). With supplied tempo/phase, preserve all valid integer pips inside
    the action, including prebeat negative pips. Grid-alignment head/tail gaps
    are recorded; endpoints are never silently extended or held.
    """
    np = _numpy()
    if not isinstance(clip, BVHClip):
        raise ScoreError('compile_bvh requires BVHClip')
    valid_name(name)
    dimensions = len(clip.profile.channels)
    integer(max_chunk_values, dimensions, min(MAX_RECORDING_VALUES, DEFAULT_CHUNK_VALUES), 'max_chunk_values')
    if source_bpm is None and source_beat_zero_seconds is not None:
        raise ScoreError('A musical beat origin requires an explicit source_bpm')
    bpm = 60. if source_bpm is None else _positive(source_bpm, 'source_bpm')
    phase = 0. if source_beat_zero_seconds is None else number(source_beat_zero_seconds, 'source_beat_zero_seconds')
    step = Fraction(60, 64) / Fraction(str(bpm))
    origin = Fraction(str(phase))
    first_pip = math.ceil(-origin / step)
    last_pip = math.floor((clip.duration_fraction - origin) / step)
    integer(first_pip, -2147483648, 2147483646, 'first source pip')
    integer(last_pip, first_pip, 2147483646, 'last source pip')
    sample_count = last_pip - first_pip + 1
    chunk_rows = max_chunk_values // dimensions
    chunk_count = (sample_count + chunk_rows - 1) // chunk_rows
    first_time, last_time = origin + first_pip * step, origin + last_pip * step
    timing_mode = 'time-only' if source_bpm is None else 'tempo-only' if source_beat_zero_seconds is None else 'tempo-and-phase'
    bpm_source = ('time-only: 60 BPM is a seconds coordinate, not a musical tempo estimate'
                  if source_bpm is None else 'Explicit source BPM supplied for BVH authoring')
    minimum = np.asarray([c.minimum for c in clip.profile.channels], dtype=np.float64)
    width = np.asarray([c.maximum - c.minimum for c in clip.profile.channels], dtype=np.float64)
    common = dict(clip.metadata, source_profile_sha256=clip.profile.fingerprint,
        clip_id=clip.source_sha256, original_clip_id=clip.source_sha256,
        timing_mode=timing_mode, musical_bpm=source_bpm,
        musical_beat_zero_seconds=source_beat_zero_seconds, total_sample_count=sample_count,
        complete_action=True, source_time_range_seconds=[0., clip.duration_seconds],
        sampled_source_time_range_seconds=[float(first_time), float(last_time)],
        grid_head_seconds=float(first_time), grid_tail_seconds=float(clip.duration_fraction - last_time),
        endpoint_policy='valid integer pip grid only; no extrapolation or endpoint hold',
        interpolation='linear local translation; shortest-path unit-quaternion SLERP',
        loop_policy='non_looping', chunk_count=chunk_count)
    for chunk_index in range(chunk_count):
        start = first_pip + chunk_index * chunk_rows
        count = min(chunk_rows, last_pip - start + 1)
        # Rational offsets prevent accumulating time drift across chunk boundaries.
        frame_start = (origin + start * step) / clip.frame_time_seconds
        frame_step = step / clip.frame_time_seconds
        positions = float(frame_start) + np.arange(count, dtype=np.float64) * float(frame_step)
        # Clip only machine-roundoff at the analytically checked exact endpoints.
        positions = np.clip(positions, 0., clip.frame_count - 1.)
        physical = _resample(clip, positions)
        samples = np.round(2. * ((physical - minimum) / width) - 1., 12)
        metadata = dict(common, chunk_index=chunk_index, chunk_start_pip=start,
                        chunk_sample_count=count,
                        chunk_source_time_range_seconds=[float(origin + start * step),
                                                         float(origin + (start + count - 1) * step)])
        suffix = f'_part_{chunk_index + 1:06d}' if chunk_count > 1 else ''
        if len(name) + len(suffix) > 128:
            raise ScoreError('BVH motion name is too long for chunk suffixes')
        clock = RecordingClock(bpm, bpm_source, 'confirmed', phase,
                               'supplied' if source_beat_zero_seconds is not None else 'unverified', start)
        yield BVHMotionChunk(name + suffix, clip.profile, samples, clock, canonical_json(metadata))
