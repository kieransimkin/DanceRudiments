#!/usr/bin/env python3
"""Real headless Blender/Rigify/native-sampler smoke test with synthetic data.

Requires bpy and the matching Python ABI's compiled DanceRudiments extension.
No motion library, model weights, music or external assets are downloaded.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring._validation import ScoreError
from dancerudiments_authoring import blender_bridge as bridge
from dancerudiments_authoring.motion import write_rig_motion
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import compile_capture
from dancerudiments_authoring.recording import RecordingClock
from dancerudiments_authoring.rigs import extend_profile, load_builtin_profile


def close(actual, expected, tolerance=1e-5):
    if abs(actual - expected) > tolerance:
        raise AssertionError(f'{actual!r} != {expected!r} within {tolerance}')


def rejected(call):
    try:
        call()
    except ScoreError:
        return
    raise AssertionError('Expected profile/target mismatch to be rejected')


def evaluated_vertices(obj):
    import bpy
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return tuple(tuple(vertex.co) for vertex in mesh.vertices)
    finally:
        evaluated.to_mesh_clear()


def verify_saved(path, rig_name, frame, expected_x, baseline):
    """Reopen with scripts disabled in a fresh process, then evaluate real skin."""
    code = '''import bpy, json, math, sys
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
path, rig_name, frame, expected_x, baseline = args
frame, expected_x, baseline = float(frame), float(expected_x), json.loads(baseline)
bpy.ops.wm.open_mainfile(filepath=path, use_scripts=False)
rig = bpy.data.objects[rig_name]
bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
bpy.context.view_layer.update()
assert abs(rig.pose.bones["root"].location.x-expected_x) < 1e-5
assert rig.animation_data.action_blend_type == "REPLACE"
assert rig.animation_data.action_influence == 1.0
assert not rig.animation_data.use_nla
obj = bpy.data.objects["SyntheticSkinnedTriangle"].evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh = obj.to_mesh()
for before, after in zip(baseline, mesh.vertices):
    assert abs(after.co.x-before[0]-expected_x) < 1e-5
    assert abs(after.co.y-before[1]) < 1e-5
    assert abs(after.co.z-before[2]) < 1e-5
obj.to_mesh_clear()
print("SAVED_POSE_AND_SKIN_VERIFIED")
'''
    arguments = [str(path), rig_name, str(frame), str(expected_x), json.dumps(baseline)]
    if Path(sys.executable).stem.lower().startswith('blender'):
        command = [sys.executable, '--background', '--factory-startup', '--python-expr', code, '--', *arguments]
    else:
        command = [sys.executable, '-c', code, *arguments]
    result = subprocess.run(command, text=True, capture_output=True, timeout=60)
    if result.returncode or 'SAVED_POSE_AND_SKIN_VERIFIED' not in result.stdout:
        raise AssertionError(f'Saved Blender playback failed:\n{result.stdout}\n{result.stderr}')


def run(output_dir):
    import bpy
    import dancerudiments
    if not hasattr(dancerudiments, 'SampledRecording'):
        raise RuntimeError('The current native DanceRudiments extension is required')
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Test the same output parent and runtime before creating test artifacts.
    with tempfile.TemporaryDirectory(prefix='preflight-', dir=output) as directory:
        old = Path(directory) / 'old'
        old.write_text('probe', encoding='ascii')
        assert old.read_text(encoding='ascii') == 'probe'
        new = old.with_name('new')
        old.rename(new)
        new.unlink()
    bridge.enable_rigify()
    report = dict(blender_version=bpy.app.version_string,
                  blender_build_hash=bpy.app.build_hash.decode('ascii'),
                  native_module=Path(dancerudiments.__file__).name,
                  source='synthetic root translation and generated Rigify basic human')
    with bridge._isolated_scene():
        module = importlib.import_module('rigify.metarigs.Basic.basic_human')
        rig = bridge._generate_model(module, component=False)
        profile = bridge.discover_profile(rig, 'Basic.basic_human', kind='metarig')
        builtin = load_builtin_profile('Basic.basic_human')
        assert profile.channels == builtin.channels
        assert profile.source['skeleton'] == builtin.source['skeleton']
        bridge.validate_target(rig, profile)
        scene = bpy.context.scene
        scene.render.fps, scene.render.fps_base = 24, 1
        # A real armature modifier and weighted mesh demonstrate skin deformation,
        # not merely assignment to a Python object with matching field names.
        mesh = bpy.data.meshes.new('SyntheticTriangle')
        mesh.from_pydata([(0, 0, 1), (0.1, 0, 1), (0, 0.1, 1)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new('SyntheticSkinnedTriangle', mesh)
        scene.collection.objects.link(obj)
        deform = next(bone.name for bone in rig.data.bones if bone.use_deform)
        obj.vertex_groups.new(name=deform).add([0, 1, 2], 1.0, 'REPLACE')
        modifier = obj.modifiers.new('RigifySkin', 'ARMATURE')
        modifier.object = rig
        baseline = evaluated_vertices(obj)
        control = rig.pose.bones['root']
        old_interpolation = bpy.context.preferences.edit.keyframe_new_interpolation_type
        try:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
            control.location.x = 0
            control.keyframe_insert(data_path='location', index=0, frame=1)
            control.location.x = 0.25
            control.keyframe_insert(data_path='location', index=0, frame=25)
        finally:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = old_interpolation
        bridge.set_action_interpolation(rig.animation_data.action, 'LINEAR')
        source_action = rig.animation_data.action
        profile_after_animation = bridge.discover_profile(rig, 'Basic.basic_human', kind='metarig')
        assert profile_after_animation.fingerprint == profile.fingerprint
        capture = bridge.capture_action(rig, profile, 1, 25)
        x_index = next(i for i, c in enumerate(profile.channels)
                       if c.binding == ('root', 'location', 0))
        close(capture.frames[0][x_index], 0)
        close(capture.frames[-1][x_index], 0.25)
        close(capture.frame_times_seconds[-1], 1)
        # Fractional glTF/FBX keyframe endpoints must remain representable.
        fractional = bridge.capture_action(rig, profile, 1.2, 1.8, frame_step=0.2)
        assert len(fractional.frames) == 4
        close(fractional.frame_times_seconds[-1], 0.6 / 24)
        close(fractional.frames[0][x_index], 0.25 * 0.2 / 24)
        close(fractional.frames[-1][x_index], 0.25 * 0.8 / 24)
        rejected(lambda: bridge.capture_action(rig, profile, 0, 10**12))
        source_map = BeatMap.from_bpm(60, beat_zero_seconds=0, source='synthetic one-second beat')
        motion = compile_capture(capture, name='rigify_smoke', source_beat_map=source_map,
                                 clock=RecordingClock(120, 'synthetic target tempo'), sample_count=65)
        player = motion.player()
        close(player.sample(32)[x_index], 0.125)
        rig.animation_data.action = None
        bridge.apply_pose(rig, profile, player.sample(32))
        moved = evaluated_vertices(obj)
        for before, after in zip(baseline, moved):
            close(after[0] - before[0], 0.125)
            close(after[1] - before[1], 0)
            close(after[2] - before[2], 0)
        # Existing profile IDs survive a newly added control property whose
        # discovery order sorts before later controls.
        control['a_test_toggle'] = False
        control.id_properties_ui('a_test_toggle').update(default=False)
        observed = bridge.discover_profile(rig, profile.model, kind='metarig')
        evolved = extend_profile(profile, observed)
        assert evolved.channels[:len(profile.channels)] == profile.channels
        assert evolved.channels[-1].value_type == 'boolean'
        bridge.validate_target(rig, evolved)
        values = list(channel.neutral for channel in evolved.channels)
        values[-1] = True
        bridge.apply_pose(rig, evolved, evolved.decode(evolved.encode(values)))
        assert control['a_test_toggle'] is True
        del control['a_test_toggle']
        rejected(lambda: bridge.validate_target(rig, evolved))
        bridge.validate_target(rig, profile)
        control.rotation_mode = 'XYZ'
        rejected(lambda: bridge.validate_target(rig, profile))
        control.rotation_mode = 'QUATERNION'
        # Exercise the actual native bake CLI with a variable-tempo target.
        motion_path = output / 'synthetic.rig-motion.json'
        write_rig_motion(motion_path, motion)
        # A hostile inherited context must not contaminate native controls.
        animation = rig.animation_data
        animation.action = source_action
        source_slot = animation.action_slot
        animation.action = None
        track = animation.nla_tracks.new()
        strip = track.strips.new('PreviousAnimation', 1, source_action)
        strip.action_slot = source_slot
        animation.action = source_action
        animation.action_slot = source_slot
        animation.action_blend_type, animation.action_influence, animation.use_nla = 'ADD', 0.5, True
        scene.frame_set(13)
        pose_path = output / 'synthetic-native-pose.blend'
        bridge.main(['apply', '--armature', rig.name, '--motion', str(motion_path),
                     '--pip', '64', '--save', str(pose_path)])
        assert source_action.use_fake_user
        verify_saved(pose_path, rig.name, 13, 0.25, baseline)
        animation.action_blend_type, animation.action_influence, animation.use_nla = 'ADD', 0.5, True
        beat_map = BeatMap(((0, 0), (0.25, 0.5), (1, 1)), source='synthetic changing target tempo')
        map_path = output / 'target-beats.json'
        map_path.write_text(json.dumps(beat_map.to_dict()), encoding='utf-8')
        blend_path = output / 'synthetic-native-rigify.blend'
        bridge.main(['bake', '--armature', rig.name, '--motion', str(motion_path),
                     '--target-beat-map', str(map_path), '--frame-start', '1', '--save', str(blend_path)])
        action = rig.animation_data.action
        close(action.frame_range[0], 1)
        close(action.frame_range[1], 25)
        curves = list(bridge.action_fcurves(action))
        assert curves
        assert all(point.interpolation == 'CONSTANT' for curve in curves for point in curve.keyframe_points)
        scene.frame_set(25)
        final = evaluated_vertices(obj)
        for before, after in zip(baseline, final):
            close(after[0] - before[0], 0.25)
        verify_saved(blend_path, rig.name, 25, 0.25, baseline)
        report.update(profile_channels=len(profile.channels), captured_frames=len(capture.frames),
                      native_pip_samples=len(motion.recording.samples), verified_skin_vertices=len(final),
                      fractional_capture=True, append_only_target_binding=True,
                      boolean_native_value_application=True, variable_tempo_native_bake=True,
                      saved_apply_and_bake_reopened=True, previous_action_nla_preserved=True,
                      bake_frame_range=list(action.frame_range))
    with bridge._isolated_scene():
        module = importlib.import_module('rigify.rigs.skin.glue')
        rig = bridge._generate_model(module, component=True)
        profile = bridge.discover_profile(rig, 'skin.glue', kind='component')
        assert profile.channels == load_builtin_profile('skin.glue', kind='component').channels
        assert profile.source['profile_context']['independent_glue_control_count'] == 0
        bridge.validate_target(rig, profile)
        report['skin_glue_context_channels'] = len(profile.channels)
    report['status'] = 'passed'
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, help='Fresh output directory for synthetic fixtures/report')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    run(args.output_dir)
