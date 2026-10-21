#!/usr/bin/env python3
"""Inspect, capture and drive actual Rigify controls from Blender.

Run with Blender's --python, or a Python environment containing official bpy.
Import/capture are authoring operations. Live playback always uses the native
DanceRudiments SampledRecording through RigMotion.player().
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
from fractions import Fraction
import hashlib
import importlib
import io
import json
import math
from pathlib import Path
import sys

from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.rigs import (
    RigChannel, RigProfile, channel_name, rig_type_uri, extend_profile,
    load_profile, write_profile,
)


def _blender():
    try:
        import bpy
    except ImportError as exc:
        raise RuntimeError('Run this bridge inside Blender or an official bpy environment') from exc
    return bpy


def enable_rigify():
    bpy = _blender()
    if 'rigify' not in bpy.context.preferences.addons:
        import addon_utils
        # default_set makes the in-memory preferences entry Rigify requires;
        # preferences are deliberately not saved to disk.
        addon_utils.enable('rigify', default_set=True, persistent=False)
    if 'rigify' not in bpy.context.preferences.addons:
        raise RuntimeError('The bundled Rigify add-on could not be enabled')
    return importlib.import_module('rigify')


def _source_metadata():
    bpy = _blender()
    rigify = enable_rigify()
    path = Path(rigify.__file__).parent
    digest = hashlib.sha256()
    for item in sorted(path.rglob('*.py')):
        digest.update(item.relative_to(path).as_posix().encode('utf-8') + b'\0')
        digest.update(item.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    version = '.'.join(str(i) for i in bpy.app.version)
    return dict(blender_version=version, blender_build_hash=bpy.app.build_hash.decode('ascii'),
                rigify_source_sha256=digest.hexdigest(),
                source_url=f'https://github.com/blender/blender/tree/v{version}/scripts/addons_core/rigify',
                coordinate_system='Blender right-handed Z-up; local pose basis relative to bone rest matrices')


def _control_bones(armature):
    return [b for b in sorted(armature.pose.bones, key=lambda b: b.name)
            if not b.name.startswith(('ORG-', 'DEF-', 'MCH-', 'VIS-'))]


def _custom_info(bone, key):
    try:
        return bone.id_properties_ui(key).as_dict()
    except (TypeError, KeyError):
        return {}


def discover_profile(armature, model, *, kind='custom', location_range=10.0,
                     rotation_range=4.0 * math.pi, scale_max=4.0):
    """Export actual animator controls, retaining rotation modes and rest basis.

    Bounds are part of the wire contract; values outside them fail on capture.
    Pose values are never used as neutral defaults or fingerprint metadata.
    """
    bpy = _blender()
    if armature.type != 'ARMATURE' or not armature.pose:
        raise ScoreError('The target must be an armature')
    for value in (location_range, rotation_range, scale_max):
        if not math.isfinite(value) or value <= 0:
            raise ScoreError('Profile transform bounds must be finite and positive')
    if scale_max < 1:
        raise ScoreError('Scale bound must contain the neutral value 1')
    channels = []

    def add(bone, path, index, unit, low, high, neutral, value_type='float', interpolation='linear', rotation_mode='', enum_items=()):
        number = len(channels) + 1
        channels.append(RigChannel(number, channel_name(number, bone.name, path, index),
                                   bone.name, path, index, unit, low, high, neutral,
                                   value_type, interpolation, rotation_mode, enum_items))

    for bone in _control_bones(armature):
        for axis in range(3):
            if not bone.lock_location[axis]:
                add(bone, 'location', axis, 'blender_unit', -location_range, location_range, 0)
        if not all(bone.lock_rotation):
            if bone.rotation_mode == 'QUATERNION':
                for axis in range(4):
                    add(bone, 'rotation_quaternion', axis, 'unitless', -1, 1,
                        1 if axis == 0 else 0, interpolation='quaternion', rotation_mode='QUATERNION')
            elif bone.rotation_mode == 'AXIS_ANGLE':
                for axis in range(4):
                    low, high = (-rotation_range, rotation_range) if axis == 0 else (-1, 1)
                    add(bone, 'rotation_axis_angle', axis, 'radian' if axis == 0 else 'unitless',
                        low, high, 1 if axis == 2 else 0, rotation_mode='AXIS_ANGLE')
            else:
                for axis in range(3):
                    if not bone.lock_rotation[axis]:
                        add(bone, 'rotation_euler', axis, 'radian', -rotation_range, rotation_range,
                            0, rotation_mode=bone.rotation_mode)
        for axis in range(3):
            if not bone.lock_scale[axis]:
                add(bone, 'scale', axis, 'unitless', 0, scale_max, 1)
        for key in sorted(bone.keys()):
            if key.startswith('_'):
                continue
            value = bone[key]
            info = _custom_info(bone, key)
            path = '[' + json.dumps(key, ensure_ascii=True) + ']'
            if isinstance(value, (bool, int, float)):
                components = [(-1, value)]
            elif hasattr(value, 'to_list') and all(isinstance(v, (bool, int, float)) for v in value):
                components = list(enumerate(value))
            else:
                continue
            defaults = info.get('default')
            for index, current in components:
                enum_items = ()
                if isinstance(current, bool):
                    value_type, low, high = 'boolean', 0, 1
                elif isinstance(current, int):
                    value_type, low, high = 'integer', info.get('min', -2147483648), info.get('max', 2147483647)
                    if info.get('items'):
                        enum_items = tuple((item[4], item[1]) for item in info['items'])
                        low, high = min(item[0] for item in enum_items), max(item[0] for item in enum_items)
                else:
                    value_type = 'float'
                    low, high = info.get('min', -1.0), info.get('max', 1.0)
                    # Generic custom properties have FLT_MAX limits that destroy
                    # useful normalized precision. A declared soft range is then
                    # the explicit export contract, otherwise require a profile edit.
                    if abs(low) > 1e12 or abs(high) > 1e12:
                        low, high = info.get('soft_min', -1.0), info.get('soft_max', 1.0)
                    if abs(low) > 1e12 or abs(high) > 1e12:
                        raise ScoreError(f'{bone.name} {key} needs explicit finite export bounds')
                if low == high:
                    continue
                if isinstance(defaults, (list, tuple)) and index >= 0:
                    neutral = defaults[index]
                elif isinstance(defaults, (int, float, bool)):
                    neutral = defaults
                else:
                    neutral = 0 if low <= 0 <= high else low
                add(bone, path, index, 'unitless', low, high, float(neutral), value_type,
                    'step' if value_type != 'float' else 'linear', enum_items=enum_items)
    source = _source_metadata()
    source['scene_unit_scale_length'] = float(bpy.context.scene.unit_settings.scale_length)
    source['transform_bounds'] = dict(location_range=location_range, rotation_range=rotation_range, scale_max=scale_max)
    source['skeleton'] = [dict(
        name=bone.name, parent=bone.parent.name if bone.parent else None,
        rest_matrix=[round(float(v), 9) for row in bone.bone.matrix_local for v in row],
        rotation_mode=bone.rotation_mode, lock_location=list(bone.lock_location),
        lock_rotation=list(bone.lock_rotation), lock_rotation_w=bool(bone.lock_rotation_w),
        lock_scale=list(bone.lock_scale), use_deform=bool(bone.bone.use_deform),
    ) for bone in sorted(armature.pose.bones, key=lambda b: b.name)]
    source['excluded_prefixes'] = ['ORG-', 'DEF-', 'MCH-', 'VIS-']
    if armature.get('dancerudiments_profile_context'):
        source['profile_context'] = json.loads(armature['dancerudiments_profile_context'])
    return RigProfile(rig_type_uri(model, kind=kind), model, tuple(channels), source_json=canonical_json(source))


def _custom_key(path):
    if path.startswith('[') and path.endswith(']'):
        try:
            key = json.loads(path[1:-1])
        except ValueError as exc:
            raise ScoreError('Invalid custom-property data path') from exc
        if isinstance(key, str) and key:
            return key
    raise ScoreError('Unsupported control data path')


def _read_channel(armature, channel):
    bone = armature.pose.bones.get(channel.bone)
    if bone is None:
        raise ScoreError(f'Missing control bone {channel.bone}')
    if channel.data_path in ('location', 'scale', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle'):
        value = getattr(bone, channel.data_path)
    else:
        value = bone[_custom_key(channel.data_path)]
    return float(value if channel.array_index == -1 else value[channel.array_index])


def validate_target(armature, profile):
    if profile.source.get('adapter') == 'dancerudiments.skeletal-source-v1':
        from .blender_import import validate_source_target
        return validate_source_target(armature, profile)
    bounds = profile.source.get('transform_bounds', {})
    kind = profile.type_uri.split('/rigify/', 1)[1].split('/', 1)[0]
    observed = discover_profile(armature, profile.model, kind=kind, **bounds)
    # Re-discovery sorts new bindings; persisted append-only profiles retain
    # their historical numbering and may have a later version number.
    by_binding = {channel.binding: channel for channel in observed.channels}
    if set(by_binding) != {channel.binding for channel in profile.channels}:
        raise ScoreError('Target control layout does not match the saved profile')
    ordered = []
    for channel in profile.channels:
        spec = by_binding[channel.binding].to_dict()
        spec.update(number=channel.number, name=channel.name)
        ordered.append(RigChannel(**spec))
    observed = RigProfile(profile.type_uri, profile.model, tuple(ordered), profile.version, observed.source_json)
    if observed.fingerprint != profile.fingerprint:
        raise ScoreError('Target rig/profile fingerprint mismatch; export this exact rig and explicitly recapture or retarget its motion')


def capture_action(armature, profile, first_frame, last_frame, *, frame_step=1):
    from dancerudiments_authoring.motion_import import RigCapture
    bpy = _blender()
    validate_target(armature, profile)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (first_frame, last_frame, frame_step)) or frame_step <= 0 or last_frame <= first_frame:
        raise ScoreError('Capture requires an increasing finite frame range and positive frame step')
    first, last, step = (Fraction(str(v)) for v in (first_frame, last_frame, frame_step))
    from dancerudiments_authoring.recording import MAX_RECORDING_VALUES
    count = (last - first) // step + 1
    if (last - first) % step:
        count += 1
    if count > MAX_RECORDING_VALUES // len(profile.channels):
        raise ScoreError('Capture exceeds the scalar budget; use a shorter excerpt or larger frame step')
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    frame_numbers = [first + index * step for index in range((last - first) // step + 1)]
    if frame_numbers[-1] != last:
        frame_numbers.append(last)
    rows = []
    times = []
    try:
        for frame in frame_numbers:
            whole_frame = math.floor(frame)
            scene.frame_set(whole_frame, subframe=float(frame - whole_frame))
            values = tuple(_read_channel(armature, c) for c in profile.channels)
            # Blender can hold slightly denormalized quaternion keyframes. Their
            # rotation meaning is normalized once at capture, before beat sampling.
            values = _normalize_quaternions(profile, values)
            profile.encode(values)  # reject range/integer errors before saving
            rows.append(values)
            times.append(float((frame - first) / Fraction(str(fps))))
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)
    provenance = dict(producer='DanceRudiments Blender Rigify bridge', source_kind='baked_rigify_action',
                      blender_frame_start=first_frame, blender_frame_end=last_frame,
                      blender_frame_step=frame_step, source_fps=fps,
                      time_origin='first captured Blender frame is 0 seconds',
                      retargeting='already performed in Blender; no name-only retargeting')
    return RigCapture(profile, tuple(times), tuple(rows), canonical_json(provenance))


def _normalize_quaternions(profile, values):
    values = list(values)
    groups = {}
    for index, channel in enumerate(profile.channels):
        if channel.interpolation == 'quaternion':
            groups.setdefault(channel.bone, []).append(index)
    for indices in groups.values():
        norm = math.sqrt(sum(values[i] ** 2 for i in indices))
        if not math.isfinite(norm) or norm < 1e-12:
            raise ScoreError('Cannot apply or capture a zero/non-finite quaternion')
        for i in indices:
            values[i] /= norm
    return tuple(values)


def apply_pose(armature, profile, values, *, frame=None):
    values = _normalize_quaternions(profile, values)
    profile.encode(values)
    if profile.source.get('adapter') == 'dancerudiments.skeletal-source-v1':
        from .blender_import import restore_source_neutral
        restore_source_neutral(armature, profile, frame=frame)
    touched = set()
    for channel, value in zip(profile.channels, values):
        bone = armature.pose.bones[channel.bone]
        if channel.data_path in ('location', 'scale', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle'):
            getattr(bone, channel.data_path)[channel.array_index] = value
        else:
            key = _custom_key(channel.data_path)
            if channel.value_type == 'integer':
                value = int(value)
            elif channel.value_type == 'boolean':
                value = bool(value)
            if channel.array_index == -1:
                bone[key] = value
            else:
                bone[key][channel.array_index] = value
        touched.add((channel.bone, channel.data_path, channel.array_index))
    if frame is not None:
        for bone_name, path, index in sorted(touched):
            armature.pose.bones[bone_name].keyframe_insert(data_path=path, index=index, frame=frame, group=bone_name)
    _blender().context.view_layer.update()


def action_fcurves(action):
    """Iterate legacy or layered Action curves without relying on UI context."""
    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        yield from legacy
        return
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type == 'KEYFRAME':
                for slot in action.slots:
                    bag = strip.channelbag(slot)
                    if bag:
                        yield from bag.fcurves


def set_action_interpolation(action, interpolation):
    # Python keyframe_insert does not consistently use the UI's new-key setting.
    for curve in action_fcurves(action):
        for point in curve.keyframe_points:
            point.interpolation = interpolation


def _flatten_metarigs(table, prefix=''):
    result = {}
    for key, value in table.items():
        if isinstance(value, dict):
            result.update(_flatten_metarigs(value, prefix + ('' if key == 'metarigs' else key + '.')))
        else:
            result[prefix + key] = value
    return result


@contextmanager
def _isolated_scene():
    bpy = _blender()
    old_scene = bpy.context.window.scene
    old_objects = set(bpy.data.objects)
    scene = bpy.data.scenes.new('DanceRudimentsProfileBuild')
    try:
        bpy.context.window.scene = scene
        yield scene
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.window.scene = old_scene
        for obj in set(bpy.data.objects) - old_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(scene)


def _generate_model(module, *, component):
    bpy = _blender()
    armature = bpy.data.armatures.new('metarig')
    obj = bpy.data.objects.new('metarig', armature)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    (module.create_sample if component else module.create)(obj)
    bpy.ops.object.mode_set(mode='OBJECT')
    glue_context = component and module.__name__.endswith('.skin.glue')
    if glue_context:
        # A glue rig deliberately has no independent control. Place a real skin
        # anchor at its head so the upstream ControlQueryNode can bind to it.
        glue = next(b for b in obj.pose.bones if b.rigify_type == 'skin.glue')
        bpy.ops.object.mode_set(mode='EDIT')
        original = armature.edit_bones[glue.name]
        anchor = armature.edit_bones.new('glue_anchor')
        anchor.head, anchor.tail, anchor.roll = original.head.copy(), original.tail.copy(), original.roll
        anchor_name = anchor.name
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.pose.bones[anchor_name].rigify_type = 'skin.anchor'
    if component:
        collection = armature.collections.new('Controls')
        collection.rigify_ui_row = 1
        for bone in armature.bones:
            collection.assign(bone)
    bpy.ops.pose.rigify_generate()
    rig = bpy.context.object
    if glue_context:
        rig['dancerudiments_profile_context'] = canonical_json(dict(
            kind='containing_rig_fixture', components=['skin.glue', 'skin.anchor'],
            independent_glue_control_count=0,
            explanation='Glue attaches to the existing skin.anchor control; channels describe that containing rig and its root.'))
    return rig


def _generation_parameters(module):
    class Collector:
        pass
    values = Collector()
    add_parameters = getattr(getattr(module, 'Rig'), 'add_parameters', None) or getattr(module, 'add_parameters', None)
    if add_parameters is None:
        return []
    add_parameters(values)
    result = []
    for name, prop in sorted(vars(values).items()):
        keywords = dict(prop.keywords)
        entry = dict(name=name, property_type=prop.function.__name__)
        for field in ('default', 'min', 'max', 'size', 'subtype'):
            if field in keywords and isinstance(keywords[field], (str, int, float, bool, list, tuple)):
                entry[field] = keywords[field]
        if isinstance(keywords.get('items'), (list, tuple)):
            entry['enum_identifiers'] = [item[0] for item in keywords['items']]
        result.append(entry)
    return result


def generate_catalogue(output_dir):
    """Build all shipped presets and all shipped component samples in Blender."""
    from dancerudiments_authoring.recording import _write_json_document
    enable_rigify()
    from rigify import metarig_menu, rig_lists
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    catalogue = dict(format='dancerudiments.rigify-catalogue', schema_version=1,
                     source=_source_metadata(), metarigs=[], components=[])
    categories = [('metarig', _flatten_metarigs(metarig_menu.metarigs)),
                  ('component', {name: value['module'] for name, value in rig_lists.rigs.items()
                                 if value.get('feature_set', 'rigify') in ('rigify', 'default')})]
    for kind, models in categories:
        for model, module in sorted(models.items()):
            entry = dict(model=model, type_uri=rig_type_uri(model, kind=kind))
            if kind == 'component':
                entry['generation_parameters'] = _generation_parameters(module)
            log = io.StringIO()
            try:
                with _isolated_scene(), redirect_stdout(log):
                    rig = _generate_model(module, component=kind == 'component')
                    profile = discover_profile(rig, model, kind=kind)
                file = kind + '_' + model.replace('.', '_').lower() + '.json'
                write_profile(directory / file, profile, overwrite=True)
                entry.update(file=file, sha256=profile.fingerprint, channel_count=len(profile.channels),
                             control_count=len({c.bone for c in profile.channels}), status='generated_and_verified')
                if profile.source.get('profile_context'):
                    entry.update(status='generated_with_context', profile_context=profile.source['profile_context'])
                print(f'{kind} {model}: {len(profile.channels)} channels', flush=True)
            except Exception as exc:
                # Every component keeps a typed catalogue entry even when it
                # needs a containing rig; never invent a control layout.
                if kind == 'metarig':
                    raise RuntimeError(f'Could not generate built-in metarig {model}: {exc}\n{log.getvalue()}') from exc
                entry.update(status='requires_containing_metarig', reason=str(exc))
                print(f'{kind} {model}: requires containing metarig ({exc})', flush=True)
            catalogue['metarigs' if kind == 'metarig' else 'components'].append(entry)
    _write_json_document(directory / 'catalogue.json', catalogue, overwrite=True)
    return catalogue


def _armature(name):
    bpy = _blender()
    obj = bpy.data.objects.get(name) if name else bpy.context.object
    if obj is None or obj.type != 'ARMATURE':
        raise ScoreError('Select an armature or specify --armature NAME')
    return obj


def _save_blend(path):
    if not path:
        return
    path = Path(path).resolve()
    if path.exists():
        raise ScoreError(f'Refusing to overwrite {path}; choose a new output file')
    path.parent.mkdir(parents=True, exist_ok=True)
    _blender().ops.wm.save_as_mainfile(filepath=str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    cat = sub.add_parser('catalogue', help='Regenerate pinned manifests using this Blender/Rigify build')
    cat.add_argument('--output-dir', required=True)
    discover = sub.add_parser('export-profile', help='Discover the active generated Rigify rig')
    discover.add_argument('--armature')
    discover.add_argument('--model', required=True)
    discover.add_argument('--kind', choices=('metarig', 'component', 'custom'), default='custom')
    discover.add_argument('--output', required=True)
    discover.add_argument('--previous', help='Preserve earlier channel numbers, appending new controls only')
    discover.add_argument('--location-range', type=float, default=10.0)
    discover.add_argument('--rotation-range', type=float, default=4.0 * math.pi)
    discover.add_argument('--scale-max', type=float, default=4.0)
    capture = sub.add_parser('capture-action', help='Capture already-retargeted control animation, without time warping')
    capture.add_argument('--armature')
    capture.add_argument('--profile', required=True)
    capture.add_argument('--frame-start', type=float)
    capture.add_argument('--frame-end', type=float)
    sampling = capture.add_mutually_exclusive_group()
    sampling.add_argument('--frame-step', type=float)
    sampling.add_argument('--sample-fps', type=float, help='Explicit source sampling rate; permits subframe sampling')
    capture.add_argument('--output', required=True)
    source = sub.add_parser('import-source', help='Use Blender importers; explicit retargeting is a separate step')
    source.add_argument('path')
    source.add_argument('--save', required=True)
    for command in ('apply', 'bake'):
        apply = sub.add_parser(command, help='Drive the rig using native DanceRudiments playback')
        apply.add_argument('--armature')
        apply.add_argument('--motion', required=True)
        apply.add_argument('--save', required=True)
        if command == 'apply':
            apply.add_argument('--pip', type=int, required=True)
        else:
            apply.add_argument('--action-name', default='DanceRudiments')
            apply.add_argument('--frame-start', type=float, default=1.0)
            apply.add_argument('--target-beat-map', help='Explicit target tempo/beat anchors for variable-tempo baking')
    args = parser.parse_args(argv)
    bpy = _blender()
    if getattr(args, 'save', None) and Path(args.save).exists():
        parser.error('--save must name a new file')
    if args.command == 'catalogue':
        generate_catalogue(args.output_dir)
    elif args.command == 'export-profile':
        profile = discover_profile(_armature(args.armature), args.model, kind=args.kind,
                                   location_range=args.location_range, rotation_range=args.rotation_range,
                                   scale_max=args.scale_max)
        if args.previous:
            profile = extend_profile(load_profile(args.previous), profile)
        write_profile(args.output, profile)
        print(json.dumps(dict(profile_sha256=profile.fingerprint, channels=len(profile.channels))))
    elif args.command == 'capture-action':
        from dancerudiments_authoring.motion_import import write_capture
        profile = load_profile(args.profile)
        scene = bpy.context.scene
        if args.sample_fps is not None and (not math.isfinite(args.sample_fps) or args.sample_fps <= 0):
            parser.error('--sample-fps must be finite and positive')
        step = ((scene.render.fps / scene.render.fps_base) / args.sample_fps
                if args.sample_fps is not None else args.frame_step if args.frame_step is not None else 1)
        capture = capture_action(_armature(args.armature), profile,
                                 args.frame_start if args.frame_start is not None else scene.frame_start,
                                 args.frame_end if args.frame_end is not None else scene.frame_end,
                                 frame_step=step)
        write_capture(args.output, capture)
        print(f'Captured {len(capture.frames)} frames')
    elif args.command == 'import-source':
        path = Path(args.path).resolve()
        if not path.is_file():
            parser.error('Source file does not exist')
        suffix = path.suffix.lower()
        if suffix == '.fbx':
            try:
                bpy.ops.wm.fbx_import.get_rna_type()
            except RuntimeError:
                bpy.ops.import_scene.fbx(filepath=str(path))
            else:
                bpy.ops.wm.fbx_import(filepath=str(path))
        elif suffix == '.bvh':
            bpy.ops.import_anim.bvh(filepath=str(path), update_scene_fps=True, update_scene_duration=True)
        elif suffix in ('.gltf', '.glb'):
            bpy.ops.import_scene.gltf(filepath=str(path))
        else:
            parser.error('Supported sources are .bvh, .fbx, .gltf and .glb')
        _save_blend(args.save)
        print('Imported source; retarget and bake to your generated Rigify controls before capture-action')
    else:
        from dancerudiments_authoring.motion import load_rig_motion
        motion = load_rig_motion(args.motion)
        rig = _armature(args.armature)
        validate_target(rig, motion.profile)
        player = motion.player()  # no pure-Python motion playback fallback
        if args.command == 'bake':
            if not math.isfinite(args.frame_start):
                parser.error('--frame-start must be finite')
            fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
            beat_map = None
            if args.target_beat_map:
                from dancerudiments_authoring.motion_clock import BeatMap
                from dancerudiments_authoring.io import read_json
                beat_map = BeatMap.from_dict(read_json(args.target_beat_map))
        rig.animation_data_create()
        animation = rig.animation_data
        old_action, old_slot = animation.action, animation.action_slot
        old_settings = {name: getattr(animation, name) for name in
                        ('action_blend_type', 'action_influence', 'action_extrapolation', 'use_nla')}
        old_fake_user = old_action.use_fake_user if old_action else None
        old_interpolation = bpy.context.preferences.edit.keyframe_new_interpolation_type
        action = bpy.data.actions.new(args.action_name if args.command == 'bake' else 'DanceRudiments Pose')
        try:
            if old_action:
                old_action.use_fake_user = True  # preserve the previous action in the saved copy
            animation.action = action
            animation.action_blend_type = 'REPLACE'
            animation.action_influence = 1.0
            animation.action_extrapolation = 'HOLD'
            animation.use_nla = False  # keep prior tracks, prevent accidental mixing
            bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'
            if args.command == 'apply':
                frame = bpy.context.scene.frame_current + bpy.context.scene.frame_subframe
                apply_pose(rig, motion.profile, player.sample(args.pip), frame=frame)
                first_frame = frame
            else:
                clock = motion.recording.clock
                origin_seconds = beat_map.seconds_at(clock.start_pip / 64) if beat_map else 0
                for index in range(len(motion.recording.samples)):
                    pip = clock.start_pip + index
                    elapsed = (beat_map.seconds_at(pip / 64) - origin_seconds
                               if beat_map else index * float(clock.pip_seconds))
                    frame = args.frame_start + elapsed * fps
                    apply_pose(rig, motion.profile, player.sample(pip), frame=frame)
                first_frame = args.frame_start
            set_action_interpolation(action, 'CONSTANT')
            whole_frame = math.floor(first_frame)
            bpy.context.scene.frame_set(whole_frame, subframe=first_frame - whole_frame)
            _save_blend(args.save)
        except Exception:
            animation.action = old_action
            if old_slot is not None:
                animation.action_slot = old_slot
            for name, value in old_settings.items():
                setattr(animation, name, value)
            if old_action:
                old_action.use_fake_user = old_fake_user
            bpy.data.actions.remove(action)
            raise
        finally:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = old_interpolation
    return 0


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(arguments))
