"""Versioned Rigify control profiles; authoring metadata, not a motion sampler.

Channel numbers are one-based persistent identifiers. Their tuple order defines
the columns of a Recording. Physical values are encoded into its existing
[-1, 1] float64 contract without clipping or guessing units.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
import re

from ._validation import ScoreError, canonical_json
from .io import read_json


PROFILE_FORMAT = 'dancerudiments.rig-profile'
_TYPE_ROOT = 'syn://type/danceflow/motion/rigify/'
_PROFILE_DIR = Path(__file__).with_name('rig_profiles')
_NAME = re.compile(r'[a-z][a-z0-9_]{0,127}\Z')
_TYPE = re.compile(r'syn://type/[a-z0-9_-]+(?:/[a-z0-9_-]+)*\Z')


def canonical_type_uri(uri: str) -> str:
    """Resolve synny:// and syn:// to the same canonical type identity."""
    if not isinstance(uri, str):
        raise ScoreError('type_uri must be a semantic type URL')
    if uri.startswith('synny://'):
        uri = 'syn://' + uri[len('synny://'):]
    if not _TYPE.fullmatch(uri):
        raise ScoreError('type_uri must be a hierarchical syn://type/ URL')
    return uri


def rig_type_uri(model: str, *, kind: str = 'metarig') -> str:
    if kind not in ('metarig', 'component', 'custom'):
        raise ScoreError('Rigify type kind must be metarig, component or custom')
    if not isinstance(model, str) or not model:
        raise ScoreError('A Rigify model identifier is required')
    parts = model.replace('/', '.').split('.')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', part) for part in parts):
        raise ScoreError('Invalid Rigify model identifier')
    return _TYPE_ROOT + kind + '/' + '/'.join(part.lower() for part in parts)


def _finite(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoreError(f'{field} must be a finite number')
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ScoreError(f'{field} must be a finite number') from exc
    if not math.isfinite(value):
        raise ScoreError(f'{field} must be a finite number')
    return value


@dataclass(frozen=True)
class RigChannel:
    number: int
    name: str
    bone: str
    data_path: str
    array_index: int
    unit: str
    minimum: float
    maximum: float
    neutral: float
    value_type: str = 'float'
    interpolation: str = 'linear'
    rotation_mode: str = ''
    enum_items: tuple[tuple[int, str], ...] = ()

    def __post_init__(self):
        if type(self.number) is not int or not 1 <= self.number <= 1_000_000:
            raise ScoreError('Channel number must be a positive integer')
        if not isinstance(self.name, str) or not _NAME.fullmatch(self.name):
            raise ScoreError('Channel name must be a Recording dimension identifier')
        if not isinstance(self.bone, str) or not self.bone or len(self.bone) > 1024:
            raise ScoreError('Channel bone must be a nonempty name')
        if not isinstance(self.data_path, str) or not self.data_path or len(self.data_path) > 2048:
            raise ScoreError('Channel data_path must be nonempty')
        if type(self.array_index) is not int or not -1 <= self.array_index <= 1024:
            raise ScoreError('Channel array_index must be -1 (scalar) or a nonnegative integer')
        if self.value_type not in ('float', 'integer', 'boolean'):
            raise ScoreError('Unsupported channel value_type')
        if self.interpolation not in ('linear', 'step', 'quaternion'):
            raise ScoreError('Unsupported channel interpolation')
        if self.value_type != 'float' and self.interpolation != 'step':
            raise ScoreError('Integer and boolean channels must use step interpolation')
        if not isinstance(self.unit, str) or not self.unit or len(self.unit) > 128:
            raise ScoreError('Channel unit is required')
        for field in ('minimum', 'maximum', 'neutral'):
            object.__setattr__(self, field, _finite(getattr(self, field), field))
        if not self.minimum < self.maximum or not math.isfinite(self.maximum - self.minimum):
            raise ScoreError('Channel range must be finite and increasing')
        if not self.minimum <= self.neutral <= self.maximum:
            raise ScoreError('Neutral value lies outside channel range')
        if self.value_type != 'float':
            if any(v != int(v) for v in (self.minimum, self.maximum, self.neutral)):
                raise ScoreError('Discrete channel ranges and neutral values must be integers')
            if self.value_type == 'boolean' and (self.minimum, self.maximum) != (0.0, 1.0):
                raise ScoreError('Boolean channel range must be [0, 1]')
            if self.maximum - self.minimum > 1e11:
                raise ScoreError('Discrete channel range exceeds normalized float64 precision budget')
        modes = ('', 'QUATERNION', 'AXIS_ANGLE', 'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX')
        if self.rotation_mode not in modes:
            raise ScoreError('Unsupported rotation mode')
        if not isinstance(self.enum_items, (tuple, list)):
            raise ScoreError('enum_items must be a sequence of [integer, label] pairs')
        items = []
        for item in self.enum_items:
            if (not isinstance(item, (tuple, list)) or len(item) != 2 or type(item[0]) is not int
                    or not isinstance(item[1], str) or not item[1] or len(item[1]) > 1024):
                raise ScoreError('Invalid discrete enum item')
            items.append(tuple(item))
        if items and (self.value_type != 'integer' or len({item[0] for item in items}) != len(items)
                      or any(not self.minimum <= item[0] <= self.maximum for item in items)
                      or self.neutral not in {item[0] for item in items}):
            raise ScoreError('Enum items must be unique in-range integer choices including the neutral value')
        object.__setattr__(self, 'enum_items', tuple(items))
        if self.data_path == 'rotation_quaternion' and self.interpolation != 'quaternion':
            raise ScoreError('Quaternion rotation channels must use grouped quaternion interpolation')
        if self.interpolation == 'quaternion' and (
                self.data_path != 'rotation_quaternion' or self.rotation_mode != 'QUATERNION'
                or self.array_index not in range(4) or (self.minimum, self.maximum) != (-1.0, 1.0)):
            raise ScoreError('Quaternion channels require wxyz components in [-1, 1]')

    @property
    def binding(self):
        return (self.bone, self.data_path, self.array_index)

    def encode(self, value: float) -> float:
        if self.value_type == 'boolean' and isinstance(value, bool):
            value = int(value)
        value = _finite(value, self.name)
        if not self.minimum <= value <= self.maximum:
            raise ScoreError(f'{self.name} value {value} is outside [{self.minimum}, {self.maximum}]; update the profile range explicitly')
        if self.value_type != 'float' and value != int(value):
            raise ScoreError(f'{self.name} requires an integer value')
        if self.enum_items and value not in {item[0] for item in self.enum_items}:
            raise ScoreError(f'{self.name} is not a declared enum choice')
        return round(2.0 * ((value - self.minimum) / (self.maximum - self.minimum)) - 1.0, 12)

    def decode(self, value: float):
        value = _finite(value, self.name)
        if not -1.0 <= value <= 1.0:
            raise ScoreError(f'{self.name} encoded value must be in [-1, 1]')
        result = self.minimum + (value + 1.0) * 0.5 * (self.maximum - self.minimum)
        # Fixed precision encoding can produce tiny representation noise. It must
        # never turn an arbitrary interpolated float into a discrete selector.
        if self.value_type != 'float':
            nearest = round(result)
            tolerance = max(1e-9, (self.maximum - self.minimum) * 1e-12)
            if abs(result - nearest) > tolerance:
                raise ScoreError(f'{self.name} decoded value is not a valid discrete value')
            if self.enum_items and nearest not in {item[0] for item in self.enum_items}:
                raise ScoreError(f'{self.name} decoded value is not a declared enum choice')
            return bool(nearest) if self.value_type == 'boolean' else nearest
        return result

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ScoreError('Channel must be an object')
        required = {'number', 'name', 'bone', 'data_path', 'array_index', 'unit', 'minimum', 'maximum', 'neutral'}
        allowed = required | {'value_type', 'interpolation', 'rotation_mode', 'enum_items'}
        if not required <= data.keys() or data.keys() - allowed:
            raise ScoreError('Invalid channel fields')
        return cls(**data)


@dataclass(frozen=True)
class RigProfile:
    type_uri: str
    model: str
    channels: tuple[RigChannel, ...]
    version: int = 1
    source_json: str = '{}'

    def __post_init__(self):
        object.__setattr__(self, 'type_uri', canonical_type_uri(self.type_uri))
        if not isinstance(self.model, str) or not self.model or len(self.model) > 1024:
            raise ScoreError('Rig profile model is required')
        if type(self.version) is not int or self.version < 1:
            raise ScoreError('Rig profile version must be a positive integer')
        channels = tuple(self.channels)
        if not 1 <= len(channels) <= 1_000_000 or any(not isinstance(c, RigChannel) for c in channels):
            raise ScoreError('Rig profile must contain RigChannels')
        if [c.number for c in channels] != list(range(1, len(channels) + 1)):
            raise ScoreError('Channels must retain contiguous one-based numbers in column order')
        if len({c.name for c in channels}) != len(channels) or len({c.binding for c in channels}) != len(channels):
            raise ScoreError('Channel names and bindings must be unique')
        groups = {}
        modes = {}
        for channel in channels:
            if channel.rotation_mode:
                if channel.bone in modes and modes[channel.bone] != channel.rotation_mode:
                    raise ScoreError('A control bone cannot declare inconsistent rotation modes')
                modes[channel.bone] = channel.rotation_mode
            if channel.interpolation == 'quaternion':
                groups.setdefault(channel.bone, set()).add(channel.array_index)
        if any(indices != {0, 1, 2, 3} for indices in groups.values()):
            raise ScoreError('Quaternion controls must include all four wxyz channels')
        object.__setattr__(self, 'channels', channels)
        try:
            source = json.loads(self.source_json)
            if not isinstance(source, dict):
                raise ValueError('source is not an object')
            object.__setattr__(self, 'source_json', canonical_json(source))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ScoreError('source_json must contain a finite JSON object') from exc

    @property
    def source(self):
        return json.loads(self.source_json)

    @property
    def dimensions(self):
        return tuple(c.name for c in self.channels)

    @property
    def fingerprint(self):
        return hashlib.sha256(canonical_json(self.to_dict()).encode('ascii')).hexdigest()

    def encode(self, values):
        values = tuple(values)
        if len(values) != len(self.channels):
            raise ScoreError('Physical pose must match profile channel count')
        encoded = tuple(c.encode(v) for c, v in zip(self.channels, values))
        self._validate_quaternions(values)
        return encoded

    def decode(self, values):
        values = tuple(values)
        if len(values) != len(self.channels):
            raise ScoreError('Encoded pose must match profile channel count')
        decoded = tuple(c.decode(v) for c, v in zip(self.channels, values))
        self._validate_quaternions(decoded)
        return decoded

    def _validate_quaternions(self, values):
        groups = {}
        for channel, value in zip(self.channels, values):
            if channel.interpolation == 'quaternion':
                groups.setdefault(channel.bone, []).append(value)
        for bone, components in groups.items():
            norm = math.sqrt(sum(value * value for value in components))
            if not math.isfinite(norm) or abs(norm - 1.0) > 1e-5:
                raise ScoreError(f'{bone} rotation must be a unit quaternion')

    def channel(self, number: int):
        if type(number) is not int or not 1 <= number <= len(self.channels):
            raise ScoreError('Unknown channel number')
        return self.channels[number - 1]

    def to_dict(self):
        return dict(format=PROFILE_FORMAT, schema_version=1, type_uri=self.type_uri,
                    model=self.model, version=self.version,
                    channels=[c.to_dict() for c in self.channels], source=self.source)

    @classmethod
    def from_dict(cls, data):
        keys = {'format', 'schema_version', 'type_uri', 'model', 'version', 'channels', 'source'}
        if not isinstance(data, dict) or data.keys() != keys or data['format'] != PROFILE_FORMAT or type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ScoreError('Invalid rig profile document')
        if not isinstance(data['channels'], list):
            raise ScoreError('Profile channels must be an array')
        return cls(data['type_uri'], data['model'], tuple(RigChannel.from_dict(c) for c in data['channels']),
                   data['version'], canonical_json(data['source']))


def extend_profile(previous: RigProfile, observed: RigProfile) -> RigProfile:
    """Append newly discovered controls, never silently renumber old channels.

    Removal, range changes or other semantic changes require an explicit new
    profile rather than silently reinterpreting an existing recording.
    """
    if previous.type_uri != observed.type_uri or previous.model != observed.model:
        raise ScoreError('Cannot extend a different rig type/model')
    by_binding = {channel.binding: channel for channel in observed.channels}
    channels = []
    for old in previous.channels:
        fresh = by_binding.pop(old.binding, None)
        if fresh is None:
            raise ScoreError(f'Existing channel removed: {old.name}; create an explicit new profile')
        old_semantics = old.to_dict()
        fresh_semantics = fresh.to_dict()
        for item in (old_semantics, fresh_semantics):
            item.pop('number')
            item.pop('name')
        if old_semantics != fresh_semantics:
            raise ScoreError(f'Existing channel changed: {old.name}; create an explicit new profile')
        channels.append(old)
    for binding in sorted(by_binding):
        fresh = by_binding[binding]
        spec = fresh.to_dict()
        spec['number'] = len(channels) + 1
        spec['name'] = channel_name(spec['number'], fresh.bone, fresh.data_path, fresh.array_index)
        channels.append(RigChannel(**spec))
    if tuple(channels) == previous.channels and observed.source_json == previous.source_json:
        return previous
    return RigProfile(previous.type_uri, previous.model, tuple(channels), previous.version + 1, observed.source_json)


def channel_name(number: int, bone: str, data_path: str, array_index: int):
    suffix = re.sub(r'[^a-z0-9]+', '_', f'{bone}_{data_path}_{array_index}'.lower()).strip('_')
    return f'c{number:06d}_{suffix}'[:128]


def load_profile(path):
    return RigProfile.from_dict(read_json(path))


def rigify_catalogue():
    """Return the checked-in, source-pinned built-in Rigify inventory."""
    return read_json(_PROFILE_DIR / 'catalogue.json')


def list_rig_profiles():
    return tuple(rigify_catalogue()['metarigs'])


def load_builtin_profile(model: str, *, kind: str = 'metarig'):
    catalogue = rigify_catalogue()
    if kind not in ('metarig', 'component'):
        raise ScoreError('Built-in profile kind must be metarig or component')
    target_uri = canonical_type_uri(model) if isinstance(model, str) and model.startswith(('syn://', 'synny://')) else None
    # Never form a filesystem path from unchecked user input.
    for entry in catalogue['metarigs' if kind == 'metarig' else 'components']:
        if model == entry['model'] or target_uri == entry['type_uri']:
            if not entry.get('file'):
                raise ScoreError(f'{model} requires a containing metarig; export its actual generated controls with Blender')
            profile = load_profile(_PROFILE_DIR / entry['file'])
            if profile.fingerprint != entry['sha256']:
                raise ScoreError('Bundled rig profile checksum mismatch')
            return profile
    raise ScoreError(f'Unknown built-in Rigify {kind}: {model}')


def builtin_rig_profile(model: str):
    return load_builtin_profile(model)


def write_profile(path, profile: RigProfile, *, overwrite=False):
    from .recording import _write_json_document
    _write_json_document(path, RigProfile.from_dict(profile.to_dict()).to_dict(), overwrite=overwrite)
