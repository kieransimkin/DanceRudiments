"""Offline skeletal Action extraction in Blender; no downloads or beat guesses.

Source skeletons have their own profile identity.  Evaluated bone transforms are
baked into a portable, constraint-free carrier; they are never labelled Rigify
controls.  Native playback remains the existing SampledRecording engine.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from ._validation import ScoreError, canonical_json
from .io import read_json
from .motion_import import RigCapture, load_capture, write_capture
from .recording import MAX_RECORDING_VALUES, _write_json_document
from .rigs import RigChannel, RigProfile, channel_name, load_profile, write_profile

SOURCE_ADAPTER = 'dancerudiments.skeletal-source-v1'
IMPORT_FORMAT = 'dancerudiments.blender-import'
_POSE_PATH = re.compile(r'^pose\.bones\[("(?:[^"\\]|\\.)*")\]')
_TRANSFORMS = ('location', 'rotation_quaternion', 'scale')
_DEFAULTS = {'location': (0., 0., 0.), 'rotation_quaternion': (1., 0., 0., 0.),
             'scale': (1., 1., 1.)}


def _bpy():
    from .blender_bridge import _blender
    return _blender()


def _matrix_values(matrix):
    return [float(value) for row in matrix for value in row]


def _matrix(values):
    from mathutils import Matrix
    if not isinstance(values, (list, tuple)) or len(values) != 16:
        raise ScoreError('Expected a 16-number row-major matrix')
    return Matrix(tuple(tuple(values[row * 4:(row + 1) * 4]) for row in range(4)))


def _finite_positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ScoreError(f'{name} must be finite and positive')
    return float(value)


def _set_frame(frame):
    whole = math.floor(frame)
    _bpy().context.scene.frame_set(whole, subframe=float(frame - whole))


def _frame_grid(first, last, step, maximum):
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (first, last, step)) or step <= 0 or last <= first:
        raise ScoreError('Extraction needs increasing finite frame bounds and a positive step')
    first, last, step = (Fraction(str(x)) for x in (first, last, step))
    count = (last - first) // step + 1 + bool((last - first) % step)
    if count > maximum:
        raise ScoreError('Capture exceeds the scalar budget; select an explicit excerpt or lower sample rate')
    for index in range((last - first) // step + 1):
        yield first + index * step
    if (last - first) % step:
        yield last


def _curves(action, slot=None):
    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        yield from legacy
        return
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type == 'KEYFRAME':
                bag = strip.channelbag(slot) if slot else None
                if bag:
                    yield from bag.fcurves


def _bone_name(path):
    match = _POSE_PATH.match(path)
    return json.loads(match.group(1)) if match else None


def _slot_id(slot):
    return slot.identifier if slot else None


def _known_users(action, slot):
    """Includes active actions and stashed NLA strips, without name guessing."""
    found = set()
    if slot and hasattr(slot, 'users'):
        found.update(slot.users())
    for obj in _bpy().context.scene.objects:
        animation = obj.animation_data
        if not animation:
            continue
        if animation.action == action and (slot is None or animation.action_slot == slot):
            found.add(obj)
        for track in animation.nla_tracks:
            for strip in track.strips:
                if strip.action == action and (slot is None or strip.action_slot == slot):
                    found.add(obj)
    return found


@dataclass(frozen=True)
class ActionBinding:
    armature: object
    action: object
    slot: object
    first_frame: float
    last_frame: float
    association: str

    @property
    def identifier(self):
        text = '\0'.join((self.armature.name, self.action.name, _slot_id(self.slot) or 'legacy'))
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def to_dict(self):
        curves = tuple(_curves(self.action, self.slot))
        return dict(id=self.identifier, armature=self.armature.name, action=self.action.name,
                    slot=_slot_id(self.slot), first_frame=self.first_frame, last_frame=self.last_frame,
                    association=self.association, curve_count=len(curves),
                    animated_bones=sorted({_bone_name(c.data_path) for c in curves if _bone_name(c.data_path)}),
                    animated_paths=sorted({c.data_path for c in curves}))


def action_bindings(armature, actions=None):
    """Discover compatible per-slot actions, returning accepted and skipped entries.

    An unbound Action needs actual bone paths that resolve on this skeleton.
    Object-only animation requires an existing explicit slot/NLA association.
    """
    if armature.type != 'ARMATURE':
        raise ScoreError('Expected an armature')
    accepted, skipped = [], []
    bones = set(armature.pose.bones.keys())
    for action in sorted(actions if actions is not None else _bpy().data.actions, key=lambda a: a.name):
        slots = list(action.slots) if hasattr(action, 'slots') else []
        for slot in slots or [None]:
            if slot and slot.target_id_type != 'OBJECT':
                continue
            curves = tuple(_curves(action, slot))
            paths = {_bone_name(c.data_path) for c in curves if _bone_name(c.data_path)}
            users = _known_users(action, slot)
            associated = armature in users
            if not associated and any(getattr(user, 'type', None) == 'ARMATURE' for user in users):
                continue
            if not associated and not paths.intersection(bones):
                continue
            missing = sorted(paths - bones)
            keyframes = [float(p.co.x) for c in curves for p in c.keyframe_points]
            if missing or not keyframes:
                skipped.append(dict(armature=armature.name, action=action.name, slot=_slot_id(slot),
                                    reason='missing source bones' if missing else 'no finite keyframes',
                                    missing_bones=missing))
                continue
            # One Action is one clip, potentially with parent/object/mesh slots.
            # Retain that shared time span rather than trimming to this slot's
            # first/last bone key and losing its object-root lead-in or endpoint.
            first, last = (float(value) for value in action.frame_range)
            if getattr(action, 'use_frame_range', False):
                first, last = float(action.frame_start), float(action.frame_end)
            if not math.isfinite(first) or not math.isfinite(last) or last <= first:
                skipped.append(dict(armature=armature.name, action=action.name, slot=_slot_id(slot),
                                    reason='action has no positive duration'))
                continue
            accepted.append(ActionBinding(armature, action, slot, first, last,
                                          'existing slot/NLA user' if associated else 'validated bone paths'))
    return accepted, skipped


def _animation_snapshot(obj):
    animation = obj.animation_data
    return dict(obj=obj, matrix_basis=obj.matrix_basis.copy(),
                pose={b.name: b.matrix_basis.copy() for b in obj.pose.bones} if obj.type == 'ARMATURE' else {},
                action=animation.action if animation else None,
                slot=animation.action_slot if animation else None,
                settings={name: getattr(animation, name) for name in
                          ('action_blend_type', 'action_influence', 'action_extrapolation', 'use_nla')}
                if animation else {})


@contextmanager
def activate_action(binding, *, allow_scene_dependencies=False):
    """Evaluate one Action with its explicit object slots; restore scene state."""
    bpy = _bpy()
    scene = bpy.context.scene
    old_frame = scene.frame_current + scene.frame_subframe
    assignments = {binding.armature: binding.slot}
    for slot in getattr(binding.action, 'slots', ()):
        if slot.target_id_type == 'OBJECT':
            for obj in _known_users(binding.action, slot):
                if isinstance(obj, bpy.types.Object) and obj.name in scene.objects:
                    if obj in assignments and assignments[obj] != slot:
                        raise ScoreError(f'Action has ambiguous slots for {obj.name}; select a single explicit binding')
                    assignments[obj] = slot
    dependencies = set()
    obj = binding.armature.parent
    while obj:
        dependencies.add(obj)
        obj = obj.parent
    for owner in (binding.armature, *binding.armature.pose.bones):
        for constraint in owner.constraints:
            target = getattr(constraint, 'target', None)
            if target:
                dependencies.add(target)
    unresolved = [obj.name for obj in dependencies - assignments.keys()
                  if obj.animation_data and (obj.animation_data.action or obj.animation_data.nla_tracks)]
    if unresolved and not allow_scene_dependencies:
        raise ScoreError('Animated dependencies are not bound to this Action: ' + ', '.join(sorted(unresolved)) +
                         '; use an explicit scene capture or --allow-scene-dependencies after review')
    snapshots = [_animation_snapshot(obj) for obj in assignments]
    try:
        for obj, slot in assignments.items():
            obj.animation_data_create()
            animation = obj.animation_data
            animation.action = binding.action
            if slot:
                animation.action_slot = slot
            animation.action_blend_type = 'REPLACE'
            animation.action_influence = 1.0
            animation.action_extrapolation = 'HOLD'
            animation.use_nla = False
        yield dict(action=binding.action.name, slot=_slot_id(binding.slot),
                   bound_objects=sorted(obj.name for obj in assignments),
                   scene_dependencies=sorted(unresolved),
                   nla_policy='individual Action; NLA disabled on assigned objects')
    finally:
        for saved in snapshots:
            obj = saved['obj']
            animation = obj.animation_data
            animation.action = saved['action']
            if saved['slot']:
                animation.action_slot = saved['slot']
            for name, value in saved['settings'].items():
                setattr(animation, name, value)
            obj.matrix_basis = saved['matrix_basis']
            for name, value in saved['pose'].items():
                obj.pose.bones[name].matrix_basis = value
        _set_frame(old_frame)


def _skeleton(armature):
    return [dict(name=b.name, parent=b.parent.name if b.parent else None,
                 rest_matrix=_matrix_values(b.matrix_local), length=float(b.length),
                 use_deform=bool(b.use_deform))
            for b in sorted(armature.data.bones, key=lambda b: b.name)]


def _decompose(matrix, context, tolerance=2e-5):
    from mathutils import Matrix
    location, rotation, scale = matrix.decompose()
    rotation.normalize()
    rebuilt = Matrix.LocRotScale(location, rotation, scale)
    error = max(abs(matrix[r][c] - rebuilt[r][c]) for r in range(4) for c in range(4))
    magnitude = max(1., max(abs(matrix[r][c]) for r in range(3) for c in range(3)))
    if not math.isfinite(error) or error > tolerance * magnitude:
        raise ScoreError(f'{context} has shear or a singular transform that local TRS channels cannot preserve (error {error:g})')
    result = tuple(float(v) for v in location) + tuple(float(v) for v in rotation) + tuple(float(v) for v in scale)
    if not all(math.isfinite(v) for v in result):
        raise ScoreError(f'{context} has non-finite transforms')
    return result


def _source_type(source_id, skeleton):
    if not isinstance(source_id, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,79}', source_id):
        raise ScoreError('source_id must be a lowercase identifier of at most 80 characters')
    digest = hashlib.sha256(canonical_json(skeleton).encode('ascii')).hexdigest()[:16]
    return f'syn://type/danceflow/motion/skeletal/source/{source_id}/skeleton_{digest}'


def extract_action(binding, *, source_id, sample_fps=None, frame_start=None, frame_end=None,
                   location_range=10000., scale_range=100., neutral_tolerance=1e-6,
                   allow_scene_dependencies=False, provenance=None):
    """Capture evaluated motion, preserving object/world motion as an extra root.

    Every source bone is preserved, including fingers and Rigify internal bones.
    Constraint results are baked; mesh morphs and B-Bone curvature are reported,
    not invented as skeletal channels. Neutral-only transform groups are omitted
    explicitly. Channels retain full wxyz groups and fixed physical bounds.
    """
    bpy = _bpy()
    armature = binding.armature
    location_range = _finite_positive(location_range, 'location_range')
    scale_range = _finite_positive(scale_range, 'scale_range')
    if scale_range < 1:
        raise ScoreError('scale_range must include neutral scale 1')
    if not isinstance(neutral_tolerance, (int, float)) or not 0 <= neutral_tolerance <= 1e-5:
        raise ScoreError('neutral_tolerance must be between 0 and 1e-5')
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    rate = _finite_positive(sample_fps if sample_fps is not None else fps, 'sample_fps')
    first = binding.first_frame if frame_start is None else frame_start
    last = binding.last_frame if frame_end is None else frame_end
    if first < binding.first_frame or last > binding.last_frame:
        raise ScoreError('Explicit extraction bounds must lie within the Action; no extrapolated choreography')
    skeleton = _skeleton(armature)
    root_name = '__dancerudiments_object__'
    while root_name in armature.data.bones:
        root_name += '_'
    from mathutils import Matrix
    skeleton.insert(0, dict(name=root_name, parent=None, rest_matrix=_matrix_values(Matrix.Identity(4)),
                           length=0.1, use_deform=False))
    for entry in skeleton[1:]:
        if entry['parent'] is None:
            entry['parent'] = root_name
    names = [entry['name'] for entry in skeleton]
    # Bound memory before making any frame list or recording rows. The temporary
    # dense evaluation also obeys the established scalar budget.
    frames = tuple(_frame_grid(first, last, fps / rate, MAX_RECORDING_VALUES // (10 * len(names))))
    rows = []
    previous_quaternions = {}
    rest_inverses = {b.name: b.matrix_local.inverted() for b in armature.data.bones}
    unsupported = []
    bent = [b.name for b in armature.data.bones if b.bbone_segments > 1]
    if bent:
        unsupported.append(dict(kind='bendy_bone_curvature', bones=bent,
                                detail='Bone transforms retained; segment curvature/handles are not skeletal TRS'))
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == armature for m in obj.modifiers):
            keys = obj.data.shape_keys
            if keys and (keys.animation_data or any(abs(k.value) > 1e-12 for k in keys.key_blocks)):
                unsupported.append(dict(kind='mesh_shape_keys', object=obj.name,
                                        detail='Morph animation is not represented by this skeletal profile'))
    with activate_action(binding, allow_scene_dependencies=allow_scene_dependencies) as action_info:
        for frame in frames:
            _set_frame(frame)
            evaluated = armature.evaluated_get(bpy.context.evaluated_depsgraph_get())
            values = list(_decompose(evaluated.matrix_world, f'{armature.name} object at frame {float(frame):g}'))
            for entry in skeleton[1:]:
                bone = evaluated.pose.bones[entry['name']]
                if bone.parent:
                    # Canonical carrier uses standard full inheritance. Its local
                    # TRS compensates for the source rig's actual evaluated pose.
                    basis = (rest_inverses[bone.name] @ bone.parent.bone.matrix_local @
                             bone.parent.matrix.inverted() @ bone.matrix)
                else:
                    basis = rest_inverses[bone.name] @ bone.matrix
                values.extend(_decompose(basis, f'{bone.name} at frame {float(frame):g}'))
            for index, name in enumerate(names):
                start = index * 10 + 3
                quat = values[start:start + 4]
                previous = previous_quaternions.get(name)
                if previous and sum(a * b for a, b in zip(previous, quat)) < 0:
                    quat = [-v for v in quat]
                    values[start:start + 4] = quat
                previous_quaternions[name] = quat
            rows.append(values)
    selected, omitted, channels = [], [], []
    for bone_index, name in enumerate(names):
        for path, offset, defaults in (('location', 0, _DEFAULTS['location']),
                                       ('rotation_quaternion', 3, _DEFAULTS['rotation_quaternion']),
                                       ('scale', 7, _DEFAULTS['scale'])):
            indices = list(range(bone_index * 10 + offset, bone_index * 10 + offset + len(defaults)))
            neutral = all(abs(row[index] - default) <= neutral_tolerance
                          for row in rows for index, default in zip(indices, defaults))
            if neutral:
                omitted.append(dict(bone=name, data_path=path, values=list(defaults)))
                continue
            for axis, index, default in zip(range(len(defaults)), indices, defaults):
                number = len(channels) + 1
                bound = location_range if path == 'location' else scale_range if path == 'scale' else 1.
                channels.append(RigChannel(number, channel_name(number, name, path, axis), name, path,
                                           axis, 'blender_unit' if path == 'location' else 'unitless',
                                           -bound, bound, default, interpolation='quaternion' if path == 'rotation_quaternion' else 'linear',
                                           rotation_mode='QUATERNION' if path == 'rotation_quaternion' else ''))
                selected.append(index)
    if not channels:
        # A legitimate held pose still needs one Recording dimension group.
        for axis in range(4):
            number = axis + 1
            channels.append(RigChannel(number, channel_name(number, root_name, 'rotation_quaternion', axis),
                                       root_name, 'rotation_quaternion', axis, 'unitless', -1, 1,
                                       1 if axis == 0 else 0, interpolation='quaternion', rotation_mode='QUATERNION'))
            selected.append(3 + axis)
        omitted = [item for item in omitted if not (item['bone'] == root_name and item['data_path'] == 'rotation_quaternion')]
    source = dict(adapter=SOURCE_ADAPTER, blender_version=bpy.app.version_string,
                  scene_unit_scale_length=float(bpy.context.scene.unit_settings.scale_length),
                  coordinate_system='Blender right-handed Z-up; preserved source bone rest bases; object/world transform on synthetic root',
                  skeleton=skeleton, object_motion_root=root_name, omitted_neutral_groups=omitted,
                  neutral_tolerance=neutral_tolerance, carrier_inheritance='FULL; local location; inherit rotation',
                  transform_bounds=dict(location_range=location_range, scale_range=scale_range))
    profile = RigProfile(_source_type(source_id, skeleton), source_id, tuple(channels),
                         source_json=canonical_json(source))
    metadata = dict(producer='DanceRudiments Blender skeletal importer', source_kind='evaluated_source_action',
                    source_fps=fps, sample_fps=rate, blender_frame_start=float(first), blender_frame_end=float(last),
                    time_origin='first captured frame is 0 seconds', action_binding=action_info,
                    range_policy='shared Action range, including all slots; no NLA strip retiming',
                    original_skeleton=_skeleton(armature), unsupported_animation=unsupported,
                    retargeting='none; portable source skeleton, not Rigify controls',
                    omitted_neutral_group_count=len(omitted), **(provenance or {}))
    times = tuple(float((frame - frames[0]) / Fraction(str(fps))) for frame in frames)
    capture = RigCapture(profile, times, tuple(tuple(row[i] for i in selected) for row in rows),
                         canonical_json(metadata))
    return capture


def create_source_armature(profile, *, name='DanceRudiments Source'):
    """Reconstruct a compatible portable carrier using only the saved profile."""
    bpy = _bpy()
    if profile.source.get('adapter') != SOURCE_ADAPTER:
        raise ScoreError('Expected a skeletal source profile')
    source = profile.source
    skeleton = source.get('skeleton')
    if not isinstance(skeleton, list) or not skeleton:
        raise ScoreError('Source profile has no portable skeleton')
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        for spec in skeleton:
            bone = data.edit_bones.new(spec['name'])
            bone.head = (0, 0, 0)
            bone.tail = (0, spec['length'], 0)
            bone.length = spec['length']
            bone.matrix = _matrix(spec['rest_matrix'])
            bone.use_deform = spec['use_deform']
        for spec in skeleton:
            bone = data.edit_bones[spec['name']]
            bone.parent = data.edit_bones[spec['parent']] if spec['parent'] else None
            bone.use_connect = False
            bone.inherit_scale = 'FULL'
            bone.use_inherit_rotation = True
            bone.use_local_location = True
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in obj.pose.bones:
            bone.rotation_mode = 'QUATERNION'
        obj['dancerudiments_source_profile_sha256'] = profile.fingerprint
        validate_source_target(obj, profile)
    except Exception:
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.armatures.remove(data)
        raise
    return obj


def validate_source_target(armature, profile):
    source = profile.source
    if source.get('adapter') != SOURCE_ADAPTER or armature.type != 'ARMATURE':
        raise ScoreError('Expected a compatible skeletal source carrier')
    expected = source['skeleton']
    if {b.name for b in armature.data.bones} != {b['name'] for b in expected}:
        raise ScoreError('Source carrier bone names differ from the saved profile')
    from mathutils import Matrix
    if max(abs(armature.matrix_world[r][c] - Matrix.Identity(4)[r][c]) for r in range(4) for c in range(4)) > 1e-6:
        raise ScoreError('Source carrier object transform must be identity; object motion belongs to its root channel')
    if armature.parent or armature.constraints:
        raise ScoreError('A source carrier must not have object parents or constraints')
    for entry in expected:
        bone = armature.data.bones[entry['name']]
        pose = armature.pose.bones[entry['name']]
        error = max(abs(a - b) for a, b in zip(_matrix_values(bone.matrix_local), entry['rest_matrix']))
        if (error > 2e-5 or abs(bone.length - entry['length']) > 2e-5
                or (bone.parent.name if bone.parent else None) != entry['parent']
                or bone.inherit_scale != 'FULL' or not bone.use_inherit_rotation or not bone.use_local_location
                or pose.rotation_mode != 'QUATERNION' or pose.constraints):
            raise ScoreError(f'Source carrier rest basis, hierarchy, mode or constraints differ at {bone.name}')
    expected_bindings = set()
    for channel in profile.channels:
        if channel.bone not in armature.pose.bones or channel.data_path not in _TRANSFORMS:
            raise ScoreError('Source profile has an unsupported binding')
        expected_bindings.add(channel.binding)
    for omitted in source.get('omitted_neutral_groups', ()):
        name, path, values = omitted['bone'], omitted['data_path'], omitted['values']
        if name not in armature.pose.bones or path not in _DEFAULTS or tuple(values) != _DEFAULTS[path]:
            raise ScoreError('Invalid omitted neutral transform declaration')
        for index in range(len(values)):
            if (name, path, index) in expected_bindings:
                raise ScoreError('Omitted and recorded source channels overlap')
            expected_bindings.add((name, path, index))
    complete = {(b['name'], path, axis) for b in expected for path, values in _DEFAULTS.items() for axis in range(len(values))}
    if expected_bindings != complete:
        raise ScoreError('Source profile must declare recorded or omitted values for every carrier transform')


def restore_source_neutral(armature, profile, *, frame=None):
    """Expand only explicitly omitted neutral groups before native pose apply."""
    for group in profile.source.get('omitted_neutral_groups', ()):
        bone = armature.pose.bones[group['bone']]
        setattr(bone, group['data_path'], group['values'])
        if frame is not None:
            bone.keyframe_insert(data_path=group['data_path'], frame=frame, group=bone.name)


def _source_layout_identity(profile):
    source = profile.source
    if source.get('adapter') != SOURCE_ADAPTER:
        raise ScoreError('Expected portable source-skeleton profiles')
    for key in ('omitted_neutral_groups', 'layout_policy'):
        source.pop(key, None)
    return (profile.type_uri, profile.model, canonical_json(source))


def _channel_semantics(channel):
    spec = channel.to_dict()
    spec.pop('number')
    spec.pop('name')
    return spec


def union_source_profile(profiles):
    """Explicitly combine compact Action layouts for one optional rig package.

    The first profile keeps its channel IDs. New bindings append deterministically.
    Existing profiles/recordings are not modified; rebind_source_capture performs
    an explicit value-preserving conversion to the returned exact profile.
    """
    profiles = tuple(profiles)
    if not profiles:
        raise ScoreError('At least one source profile is required')
    first = profiles[0]
    identity = _source_layout_identity(first)
    bindings = {channel.binding: channel for channel in first.channels}
    for profile in profiles[1:]:
        if _source_layout_identity(profile) != identity:
            raise ScoreError('Source profile union requires the same exact skeleton, units, bounds and adapter metadata')
        for channel in profile.channels:
            old = bindings.get(channel.binding)
            if old and _channel_semantics(old) != _channel_semantics(channel):
                raise ScoreError('Source profiles assign different semantics to the same binding')
            bindings[channel.binding] = channel
    if set(bindings) == {c.binding for c in first.channels}:
        return first
    channels = list(first.channels)
    for binding in sorted(set(bindings) - {c.binding for c in first.channels}):
        channel = bindings[binding]
        number = len(channels) + 1
        spec = channel.to_dict()
        spec.update(number=number, name=channel_name(number, *binding))
        channels.append(RigChannel(**spec))
    source = first.source
    source['omitted_neutral_groups'] = [
        item for item in source['omitted_neutral_groups']
        if not any((item['bone'], item['data_path'], index) in bindings for index in range(len(item['values'])))
    ]
    source['layout_policy'] = 'explicit source Action union; first profile IDs preserved and missing bindings appended'
    return RigProfile(first.type_uri, first.model, tuple(channels), max(p.version for p in profiles) + 1,
                      canonical_json(source))


def rebind_source_capture(capture, profile):
    """Expand declared neutral values and reorder columns to an explicit union."""
    if _source_layout_identity(capture.profile) != _source_layout_identity(profile):
        raise ScoreError('Capture and destination do not describe the same exact source skeleton')
    old = {channel.binding: (index, channel) for index, channel in enumerate(capture.profile.channels)}
    destination = {channel.binding: channel for channel in profile.channels}
    if not set(old) <= set(destination):
        raise ScoreError('Source rebind cannot discard recorded bindings')
    for binding, (_, channel) in old.items():
        if _channel_semantics(channel) != _channel_semantics(destination[binding]):
            raise ScoreError('Source rebind cannot change units, bounds or interpolation')
    neutral = {(group['bone'], group['data_path'], index): value
               for group in capture.profile.source['omitted_neutral_groups']
               for index, value in enumerate(group['values'])}
    if set(destination) - set(old) - set(neutral):
        raise ScoreError('Source rebind can only expand explicitly omitted neutral channels')
    if len(capture.frames) > MAX_RECORDING_VALUES // len(profile.channels):
        raise ScoreError('Expanded source capture exceeds the scalar budget')
    rows = tuple(tuple(row[old[channel.binding][0]] if channel.binding in old else neutral[channel.binding]
                       for channel in profile.channels) for row in capture.frames)
    provenance = dict(capture.provenance, source_layout_rebound_from=capture.profile.fingerprint)
    return RigCapture(profile, capture.frame_times_seconds, rows, canonical_json(provenance))


def _validate_fk_map(mapping, source_profile, target_profile):
    required = {'format', 'schema_version', 'source_type_uri', 'target_profile_sha256',
                'source_reference_object_matrix', 'source_to_target_rotation',
                'root_translation_scale', 'bones', 'setup'}
    if (not isinstance(mapping, dict) or set(mapping) != required
            or mapping['format'] != 'dancerudiments.fk-map' or mapping['schema_version'] != 1):
        raise ScoreError('Expected a complete dancerudiments.fk-map schema 1 document')
    if mapping['source_type_uri'] != source_profile.type_uri or mapping['target_profile_sha256'] != target_profile.fingerprint:
        raise ScoreError('FK map source type or exact target profile does not match')
    reference = _matrix(mapping['source_reference_object_matrix'])
    reference_values = _decompose(reference, 'source reference object matrix')
    if any(abs(value - 1) > 1e-6 for value in reference_values[7:]):
        raise ScoreError('Source reference matrix must be rigid; use root_translation_scale for unit/proportion scaling')
    from mathutils import Quaternion
    rotation = mapping['source_to_target_rotation']
    if (not isinstance(rotation, list) or len(rotation) != 4
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in rotation)
            or abs(sum(x * x for x in rotation) - 1) > 1e-5):
        raise ScoreError('source_to_target_rotation must be an explicit unit wxyz quaternion')
    alignment = Quaternion(rotation).normalized()
    scale = _finite_positive(mapping['root_translation_scale'], 'root_translation_scale')
    if not isinstance(mapping['bones'], list) or not mapping['bones']:
        raise ScoreError('FK map must explicitly name at least one source and target bone')
    source_names = {entry['name'] for entry in source_profile.source['skeleton']}
    target_names = {c.bone for c in target_profile.channels}
    seen, translations = set(), 0
    for item in mapping['bones']:
        if (not isinstance(item, dict) or set(item) != {'source', 'target', 'rotation', 'translation'}
                or item['source'] not in source_names or item['target'] not in target_names
                or type(item['rotation']) is not bool or type(item['translation']) is not bool
                or not (item['rotation'] or item['translation']) or item['target'] in seen):
            raise ScoreError('FK map entries need existing bones, unique targets and explicit rotation/translation booleans')
        seen.add(item['target'])
        translations += item['translation']
    if translations > 1:
        raise ScoreError('FK mapping supports one explicit root translation, not an implicit IK solver')
    if not isinstance(mapping['setup'], list):
        raise ScoreError('FK setup must be a list of explicit channel values')
    setup = {}
    for item in mapping['setup']:
        if not isinstance(item, dict) or set(item) != {'channel_number', 'value'}:
            raise ScoreError('FK setup entries require channel_number and value')
        channel = target_profile.channel(item['channel_number'])
        if channel.number in setup:
            raise ScoreError('Duplicate FK setup channel')
        channel.encode(item['value'])
        setup[channel.number] = item['value']
    return reference, alignment, scale, setup


def _assign_basis(bone, matrix):
    from mathutils import Quaternion
    values = _decompose(matrix, f'target control {bone.name}')
    bone.location = values[:3]
    rotation = Quaternion(values[3:7])
    if bone.rotation_mode == 'QUATERNION':
        bone.rotation_quaternion = rotation
    elif bone.rotation_mode == 'AXIS_ANGLE':
        axis, angle = rotation.to_axis_angle()
        bone.rotation_axis_angle = (angle, *axis)
    else:
        bone.rotation_euler = rotation.to_euler(bone.rotation_mode, bone.rotation_euler)
    bone.scale = values[7:]


def retarget_capture(capture, target, target_profile, mapping):
    """Explicit rest-aware FK authoring into an exact generated Rigify rig.

    Source/world rotation deltas are aligned and applied to target rest axes.
    One declared root can translate with an explicit scale. FK/IK properties are
    supplied by numbered setup channels. This does not solve poles, IK, contacts,
    morphs, missing fingers, or unmatched joints. Those remain in the report.
    """
    if capture.profile.source.get('adapter') != SOURCE_ADAPTER:
        raise ScoreError('FK retargeting expects a portable source-skeleton capture')
    if '/rigify/' not in target_profile.type_uri:
        raise ScoreError('FK target must be an explicitly exported Rigify control profile')
    from . import blender_bridge as bridge
    bridge.validate_target(target, target_profile)
    reference, alignment, scale, setup = _validate_fk_map(mapping, capture.profile, target_profile)
    if len(capture.frames) > MAX_RECORDING_VALUES // len(target_profile.channels):
        raise ScoreError('Retargeted capture exceeds the scalar budget; extract an explicit excerpt first')
    bpy = _bpy()
    from mathutils import Matrix
    source = create_source_armature(capture.profile, name='DanceRudiments Retarget Source')
    snapshot = _animation_snapshot(target)
    before = tuple(bridge._read_channel(target, channel) for channel in target_profile.channels)
    target.animation_data_create()
    animation = target.animation_data
    old_frame = bpy.context.scene.frame_current + bpy.context.scene.frame_subframe
    source_rest = {entry['name']: reference @ _matrix(entry['rest_matrix'])
                   for entry in capture.profile.source['skeleton']}
    target_world = target.matrix_world.copy()
    target_world_inverse = target_world.inverted()
    target_rest = {bone.name: target_world @ bone.bone.matrix_local for bone in target.pose.bones}
    ordered = sorted(mapping['bones'], key=lambda item: len(target.pose.bones[item['target']].parent_recursive))
    covered = {(channel.bone, channel.data_path, channel.array_index) for channel in target_profile.channels}
    initial = [setup.get(channel.number, channel.neutral) for channel in target_profile.channels]
    rows, maximum_error = [], 0.
    try:
        animation.action = None
        animation.use_nla = False
        animation.action_blend_type, animation.action_influence = 'REPLACE', 1.
        bridge.apply_pose(target, target_profile, initial)
        baseline = {item['target']: target.pose.bones[item['target']].matrix_basis.copy() for item in ordered}
        baseline_rotations = {}
        for item in ordered:
            bone = target.pose.bones[item['target']]
            path = ('rotation_quaternion' if bone.rotation_mode == 'QUATERNION' else
                    'rotation_axis_angle' if bone.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler')
            baseline_rotations[bone.name] = tuple(getattr(bone, path))
        for values in capture.frames:
            bridge.apply_pose(source, capture.profile, values)
            for item in ordered:
                source_matrix = source.pose.bones[item['source']].matrix.copy()
                rest = source_rest[item['source']]
                target_bone = target.pose.bones[item['target']]
                current = target_world @ target_bone.matrix
                location, rotation, current_scale = current.decompose()
                desired_rotation = None
                if item['rotation']:
                    delta = source_matrix.to_quaternion() @ rest.to_quaternion().inverted()
                    desired_rotation = (alignment @ delta @ alignment.inverted() @
                                        target_rest[target_bone.name].to_quaternion()).normalized()
                    rotation = desired_rotation
                if item['translation']:
                    location = (target_rest[target_bone.name].translation +
                                alignment @ (source_matrix.translation - rest.translation) * scale)
                desired = target_world_inverse @ Matrix.LocRotScale(location, rotation, current_scale)
                kwargs = dict(parent_matrix=target_bone.parent.matrix,
                              parent_matrix_local=target_bone.parent.bone.matrix_local) if target_bone.parent else {}
                basis = target_bone.bone.convert_local_to_pose(desired, target_bone.bone.matrix_local,
                                                               invert=True, **kwargs)
                _assign_basis(target_bone, basis)
                # A locked/unexported parameter cannot silently become a second
                # pose source outside the declared numbered channel contract.
                old = _decompose(baseline[target_bone.name], target_bone.name)
                new = _decompose(target_bone.matrix_basis, target_bone.name)
                mode = target_bone.rotation_mode
                for path, a, b in (('location', old[:3], new[:3]), ('scale', old[7:], new[7:])):
                    if any(abs(x - y) > 2e-5 and (target_bone.name, path, axis) not in covered
                           for axis, (x, y) in enumerate(zip(a, b))):
                        raise ScoreError(f'FK map needs a transform absent from the target profile: {target_bone.name} {path}')
                rotation_path = 'rotation_quaternion' if mode == 'QUATERNION' else 'rotation_axis_angle' if mode == 'AXIS_ANGLE' else 'rotation_euler'
                if item['rotation'] and not any(c.bone == target_bone.name and c.data_path == rotation_path for c in target_profile.channels):
                    raise ScoreError(f'Target rotation is not an exported control: {target_bone.name}')
                if any(abs(a - b) > 2e-5 and (target_bone.name, rotation_path, axis) not in covered
                       for axis, (a, b) in enumerate(zip(baseline_rotations[target_bone.name],
                                                        getattr(target_bone, rotation_path)))):
                    raise ScoreError(f'FK mapping needs an unexported rotation component: {target_bone.name}')
                bpy.context.view_layer.update()
                if desired_rotation is not None:
                    actual = (target_world @ target_bone.matrix).to_quaternion()
                    cosine = min(1., max(-1., abs(actual.dot(desired_rotation))))
                    error = 2 * math.acos(cosine)
                    maximum_error = max(maximum_error, error)
                    if error > 0.003:
                        raise ScoreError(f'Target control {target_bone.name} cannot reach the mapped FK rotation; check constraints and FK setup')
            row = bridge._normalize_quaternions(target_profile,
                                                tuple(bridge._read_channel(target, c) for c in target_profile.channels))
            target_profile.encode(row)
            rows.append(row)
    finally:
        bridge.apply_pose(target, target_profile, before)
        animation.action = snapshot['action']
        if snapshot['slot']:
            animation.action_slot = snapshot['slot']
        for name, value in snapshot['settings'].items():
            setattr(animation, name, value)
        for name, matrix in snapshot['pose'].items():
            target.pose.bones[name].matrix_basis = matrix
        data = source.data
        bpy.data.objects.remove(source, do_unlink=True)
        bpy.data.armatures.remove(data)
        _set_frame(old_frame)
    mapped_sources = {item['source'] for item in mapping['bones']}
    mapped_targets = {item['target'] for item in mapping['bones']}
    report = dict(method='explicit FK world-rest rotation deltas and one scaled root; no IK/contact solver',
                  source_scale_policy='source scale animation is retained in the source capture; target FK scales remain at their explicit baseline',
                  mapping_sha256=hashlib.sha256(canonical_json(mapping).encode('ascii')).hexdigest(),
                  mapping=mapping, maximum_control_angle_error_radians=maximum_error,
                  unmapped_source_bones=sorted(set(source_rest) - mapped_sources),
                  unmapped_target_channel_numbers=[c.number for c in target_profile.channels
                                                   if c.bone not in mapped_targets and c.number not in setup],
                  fixed_setup_channel_numbers=sorted(setup), target_object_matrix=_matrix_values(target_world))
    provenance = dict(capture.provenance, source_profile_sha256=capture.profile.fingerprint,
                      source_capture_sha256=capture.fingerprint, retargeting=report,
                      source_kind='explicitly_retargeted_rigify_fk_action')
    return RigCapture(target_profile, capture.frame_times_seconds, tuple(rows), canonical_json(provenance))


@contextmanager
def imported_scene(path, *, scene_name=None, axis_forward='-Z', axis_up='Y', global_scale=1.):
    """Load one local source in an isolated scene; never execute embedded scripts."""
    bpy = _bpy()
    path = Path(path).resolve()
    if not path.is_file():
        raise ScoreError('Source file does not exist')
    suffix = path.suffix.lower()
    if suffix not in ('.bvh', '.fbx', '.glb', '.gltf', '.blend'):
        raise ScoreError('Supported sources are BVH, FBX, glTF/GLB and BLEND')
    _finite_positive(global_scale, 'global_scale')
    if suffix != '.bvh' and (axis_forward != '-Z' or axis_up != 'Y'):
        raise ScoreError('Explicit source-axis flags apply to BVH; FBX/glTF/BLEND carry their own axes')
    if suffix in ('.blend', '.gltf', '.glb') and global_scale != 1:
        raise ScoreError('This format carries its own scale; use an explicit retarget scale')
    old_scene = bpy.context.window.scene
    old_objects, old_scenes, old_actions = set(bpy.data.objects), set(bpy.data.scenes), set(bpy.data.actions)
    old_autoexecute = bpy.context.preferences.filepaths.use_scripts_auto_execute
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    try:
        if suffix == '.blend':
            with bpy.data.libraries.load(str(path), link=False) as (available, loaded):
                if scene_name is None and len(available.scenes) != 1:
                    raise ScoreError('BLEND has multiple scenes; select --scene explicitly: ' + ', '.join(available.scenes))
                selected = scene_name if scene_name is not None else available.scenes[0]
                if selected not in available.scenes:
                    raise ScoreError('Requested source scene does not exist')
                loaded.scenes = [selected]
                loaded.actions = list(available.actions)
            scene = loaded.scenes[0]
            bpy.context.window.scene = scene
        else:
            scene = bpy.data.scenes.new('DanceRudiments Import')
            bpy.context.window.scene = scene
            if suffix == '.bvh':
                bpy.ops.import_anim.bvh(filepath=str(path), update_scene_fps=True, update_scene_duration=True,
                                        global_scale=global_scale, axis_forward=axis_forward, axis_up=axis_up)
            elif suffix == '.fbx':
                try:
                    bpy.ops.wm.fbx_import.get_rna_type()
                except (AttributeError, RuntimeError):
                    bpy.ops.import_scene.fbx(filepath=str(path), global_scale=global_scale)
                else:
                    bpy.ops.wm.fbx_import(filepath=str(path), global_scale=global_scale)
            else:
                if global_scale != 1:
                    raise ScoreError('glTF scale is defined by its file; use an explicit retarget scale')
                bpy.ops.import_scene.gltf(filepath=str(path))
        bpy.context.view_layer.update()
        yield scene, tuple(set(bpy.data.actions) - old_actions)
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.window.scene = old_scene
        for obj in set(bpy.data.objects) - old_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for scene in set(bpy.data.scenes) - old_scenes:
            bpy.data.scenes.remove(scene)
        for action in set(bpy.data.actions) - old_actions:
            bpy.data.actions.remove(action)
        bpy.context.preferences.filepaths.use_scripts_auto_execute = old_autoexecute


def inspect_scene(scene, actions):
    accepted, skipped = [], []
    for armature in sorted((obj for obj in scene.objects if obj.type == 'ARMATURE'), key=lambda obj: obj.name):
        bindings, rejected = action_bindings(armature, actions)
        accepted.extend(bindings)
        skipped.extend(rejected)
    return accepted, dict(format=IMPORT_FORMAT, schema_version=1, blender_version=_bpy().app.version_string,
                          scene=scene.name, source_fps=scene.render.fps / scene.render.fps_base,
                          armatures=[dict(name=obj.name, bones=len(obj.data.bones)) for obj in scene.objects if obj.type == 'ARMATURE'],
                          actions=[binding.to_dict() for binding in accepted], skipped=skipped)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('inspect', 'extract'):
        options = sub.add_parser(command)
        options.add_argument('input')
        options.add_argument('--scene')
        options.add_argument('--axis-forward', default='-Z')
        options.add_argument('--axis-up', default='Y')
        options.add_argument('--global-scale', type=float, default=1.)
        if command == 'inspect':
            options.add_argument('--output', required=True)
        else:
            options.add_argument('--source-id', required=True)
            options.add_argument('--output-dir', required=True)
            options.add_argument('--armature', action='append')
            options.add_argument('--action', action='append')
            options.add_argument('--binding-id', action='append')
            options.add_argument('--sample-fps', type=float)
            options.add_argument('--frame-start', type=float)
            options.add_argument('--frame-end', type=float)
            options.add_argument('--location-range', type=float, default=10000.)
            options.add_argument('--scale-range', type=float, default=100.)
            options.add_argument('--neutral-tolerance', type=float, default=1e-6,
                                 help='Explicit near-neutral TRS omission tolerance (0 to 1e-5)')
            options.add_argument('--allow-scene-dependencies', action='store_true')
            options.add_argument('--continue-on-error', action='store_true')
    retarget = sub.add_parser('retarget', help='Apply an explicit rest-aware FK map to an exact Rigify profile')
    retarget.add_argument('capture')
    retarget.add_argument('--target-blend', required=True)
    retarget.add_argument('--scene')
    retarget.add_argument('--target-armature', required=True)
    retarget.add_argument('--target-profile', required=True)
    retarget.add_argument('--mapping', required=True)
    retarget.add_argument('--output', required=True)
    carrier = sub.add_parser('create-carrier', help='Reconstruct a compatible source skeleton from its profile')
    carrier.add_argument('profile')
    carrier.add_argument('--name', default='DanceRudiments Source')
    carrier.add_argument('--save', required=True)
    args = parser.parse_args(argv)
    if args.command == 'retarget':
        output = Path(args.output).resolve()
        if output.exists():
            raise ScoreError('Output must name a new capture file')
        capture = load_capture(args.capture)
        profile, mapping = load_profile(args.target_profile), read_json(args.mapping)
        with imported_scene(args.target_blend, scene_name=args.scene) as (scene, _):
            target = scene.objects.get(args.target_armature)
            if target is None or target.type != 'ARMATURE':
                raise ScoreError('Requested target armature does not exist in the selected scene')
            result = retarget_capture(capture, target, profile, mapping)
            write_capture(output, result)
        print(json.dumps(dict(output=str(output), frame_count=len(result.frames),
                              profile_sha256=result.profile.fingerprint)))
        return 0
    if args.command == 'create-carrier':
        from .blender_bridge import _save_blend
        if Path(args.save).exists():
            raise ScoreError('Output must name a new Blender file')
        profile = load_profile(args.profile)
        rig = create_source_armature(profile, name=args.name)
        _save_blend(args.save)
        print(json.dumps(dict(armature=rig.name, profile_sha256=profile.fingerprint)))
        return 0
    path = Path(args.input).resolve()
    output = Path(args.output if args.command == 'inspect' else args.output_dir).resolve()
    if output.exists():
        raise ScoreError('Output must name a new file or directory')
    with imported_scene(path, scene_name=args.scene, axis_forward=args.axis_forward,
                        axis_up=args.axis_up, global_scale=args.global_scale) as (scene, actions):
        bindings, report = inspect_scene(scene, actions)
        report['source'] = dict(filename=path.name, sha256=_file_sha256(path),
                                import_options=dict(axis_forward=args.axis_forward, axis_up=args.axis_up,
                                                    global_scale=args.global_scale),
                                external_resources='glTF external buffers/textures are not hashed' if path.suffix.lower() == '.gltf' else None)
        if args.command == 'inspect':
            _write_json_document(output, report)
        else:
            output.mkdir(parents=True)
            chosen = [b for b in bindings if (not args.armature or b.armature.name in args.armature)
                      and (not args.action or b.action.name in args.action)
                      and (not args.binding_id or b.identifier in args.binding_id)]
            if not chosen:
                raise ScoreError('No compatible positive-duration Actions match the selection')
            report['captures'], report['failures'] = [], []
            for binding in chosen:
                try:
                    capture = extract_action(binding, source_id=args.source_id, sample_fps=args.sample_fps,
                                             frame_start=args.frame_start, frame_end=args.frame_end,
                                             location_range=args.location_range, scale_range=args.scale_range,
                                             neutral_tolerance=args.neutral_tolerance,
                                             allow_scene_dependencies=args.allow_scene_dependencies,
                                             provenance=dict(source_file=report['source']))
                    stem = binding.identifier
                    write_capture(output / f'{stem}.capture.json', capture)
                    write_profile(output / f'{stem}.profile.json', capture.profile)
                    report['captures'].append(dict(binding_id=stem, action=binding.action.name,
                                                   armature=binding.armature.name, slot=_slot_id(binding.slot),
                                                   capture=f'{stem}.capture.json', profile=f'{stem}.profile.json',
                                                   profile_sha256=capture.profile.fingerprint,
                                                   frame_count=len(capture.frames), channel_count=len(capture.profile.channels),
                                                   duration_seconds=capture.frame_times_seconds[-1],
                                                   unsupported_animation=capture.provenance['unsupported_animation']))
                except (ScoreError, RuntimeError, ValueError) as exc:
                    report['failures'].append(dict(binding_id=binding.identifier, action=binding.action.name,
                                                   error=f'{type(exc).__name__}: {exc}'))
                    if not args.continue_on_error:
                        _write_json_document(output / 'index.json', report)
                        raise
            _write_json_document(output / 'index.json', report)
    print(json.dumps(dict(output=str(output), actions=len(report['actions']),
                          extracted=len(report.get('captures', ())), failed=len(report.get('failures', ())))))
    return 0 if not report.get('failures') else 2


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(arguments))
