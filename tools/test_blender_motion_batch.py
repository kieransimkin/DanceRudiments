#!/usr/bin/env python3
"""Real Blender regression for source Actions, compact carriers and FK maps.

All fixtures are created locally. No models, motion assets or music are fetched.
Requires the pinned bpy environment and its matching native extension.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring import blender_bridge as bridge
from dancerudiments_authoring import blender_import as importer
from dancerudiments_authoring.motion import write_rig_motion
from dancerudiments_authoring.motion_clock import BeatMap
from dancerudiments_authoring.motion_import import compile_capture
from dancerudiments_authoring.recording import RecordingClock
from dancerudiments_authoring._validation import ScoreError


def close(a, b, tolerance=3e-5):
    if not math.isfinite(a) or abs(a - b) > tolerance:
        raise AssertionError(f'{a} != {b} within {tolerance}')


def matrix_error(a, b):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))


def vertices(obj):
    import bpy
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [list(evaluated.matrix_world @ v.co) for v in evaluated.data.vertices]


def skin(rig, bone, name):
    import bpy
    from mathutils import Vector
    rest = rig.data.bones[bone].matrix_local
    points = [rest @ Vector(p) for p in ((0, .15, 0), (.04, .15, 0), (0, .2, .03))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], [(0, 1, 2)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.vertex_groups.new(name=bone).add([0, 1, 2], 1, 'REPLACE')
    obj.modifiers.new('Skin', 'ARMATURE').object = rig
    return obj


def fixture():
    import bpy
    from mathutils import Quaternion
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = 30, 1
    bpy.ops.object.armature_add(enter_editmode=True)
    rig = bpy.context.object
    rig.name = 'SourceThreeBones'
    root = rig.data.edit_bones[0]
    root.name, root.head, root.tail = 'Hips', (0, 0, 0), (0, 1, 0)
    upper = rig.data.edit_bones.new('Upper')
    upper.head, upper.tail, upper.parent = (0, 1, 0), (.6, 1.7, .2), root
    upper.roll = .31
    finger = rig.data.edit_bones.new('Finger')
    finger.head, finger.tail, finger.parent = upper.tail, (.8, 1.9, .3), upper
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = Quaternion((0, 0, 1), .4)
    rig.location = (3, 4, 0)
    reference = rig.matrix_world.copy()
    bpy.context.view_layer.update()
    reference = rig.matrix_world.copy()
    actions = []
    for name, vertical in (('Walk with fingers', False), ('Jump with fingers', True)):
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        rig.animation_data_create()
        rig.animation_data.action = action
        for frame, amount in ((1., 0.), (16., .5), (31., 1.)):
            rig.location = (3 + (0 if vertical else 2 * amount), 4, amount if vertical else 0)
            rig.keyframe_insert(data_path='location', frame=frame)
            rig.pose.bones['Upper'].rotation_quaternion = Quaternion((0, 1, 0), .6 * amount)
            rig.pose.bones['Upper'].keyframe_insert(data_path='rotation_quaternion', frame=frame)
            rig.pose.bones['Finger'].rotation_quaternion = Quaternion((0, 0, 1), -.5 * amount)
            rig.pose.bones['Finger'].keyframe_insert(data_path='rotation_quaternion', frame=frame)
        bridge.set_action_interpolation(action, 'LINEAR')
        actions.append(action)
    rig.animation_data.action = actions[0]
    rig.animation_data.action_slot = actions[0].slots[0]
    scene.frame_set(1)
    return rig, actions, reference


def native_motion(capture, name):
    # Synthetic duration clock only; this is intentionally not inferred music.
    origin = 'synthetic regression duration clock; not musical beat detection'
    return compile_capture(capture, name=name,
                           source_beat_map=BeatMap.from_bpm(60, beat_zero_seconds=0, source=origin),
                           clock=RecordingClock(60, origin), sample_count=65)


def reopen_mesh(path, object_name, expected):
    code = '''import bpy,json,sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[1],use_scripts=False)
bpy.context.view_layer.update()
obj=bpy.data.objects[sys.argv[2]].evaluated_get(bpy.context.evaluated_depsgraph_get())
print('EVIDENCE:'+json.dumps([list(obj.matrix_world@v.co) for v in obj.data.vertices]))
'''
    result = subprocess.run([sys.executable, '-c', code, str(path), object_name],
                            check=True, capture_output=True, text=True)
    actual = json.loads(next(line[len('EVIDENCE:'):] for line in result.stdout.splitlines() if line.startswith('EVIDENCE:')))
    for got, want in zip(actual, expected):
        for a, b in zip(got, want):
            close(a, b)


def run(output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='preflight-', dir=output) as directory:
        p = Path(directory) / 'probe'
        p.write_bytes(b'probe')
        assert p.read_bytes() == b'probe'
        q = p.with_name('renamed')
        p.rename(q)
        assert q.read_bytes() == b'probe'
        q.unlink()
    import bpy
    import dancerudiments
    assert hasattr(dancerudiments, 'SampledRecording')
    report = dict(blender_version=bpy.app.version_string, source='original synthetic motion only', status='failed')
    try:
        with tempfile.TemporaryDirectory(prefix='fixtures-', dir=output) as folder:
            work = Path(folder)
            with bridge._isolated_scene() as scene:
                rig, actions, reference = fixture()
                bindings, skipped = importer.action_bindings(rig, actions)
                assert len(bindings) == 2 and not skipped
                capture = next(importer.extract_action(b, source_id='synthetic_batch', sample_fps=30)
                               for b in bindings if b.action.name == 'Walk with fingers')
                assert len(capture.frames) == 31 and len(capture.profile.channels) == 15
                assert len(capture.profile.source['omitted_neutral_groups']) == 8
                assert any(c.bone == 'Finger' for c in capture.profile.channels)
                carrier = importer.create_source_armature(capture.profile, name='Portable Source Carrier')
                binding = next(b for b in bindings if b.action.name == 'Walk with fingers')
                maximum_error = 0.
                with importer.activate_action(binding):
                    for index in (0, 15, 30):
                        scene.frame_set(index + 1)
                        bridge.apply_pose(carrier, capture.profile, capture.frames[index])
                        for bone in rig.pose.bones:
                            expected = rig.matrix_world @ bone.matrix
                            actual = carrier.pose.bones[bone.name].matrix
                            maximum_error = max(maximum_error, matrix_error(actual, expected))
                assert maximum_error < 3e-5, maximum_error
                # Omitted neutral groups are expanded, rather than retaining a
                # previous arbitrary pose when another compact clip is applied.
                carrier.pose.bones['Hips'].location = (9, 8, 7)
                bridge.apply_pose(carrier, capture.profile, capture.frames[0])
                close(carrier.pose.bones['Hips'].location.length, 0)
                importer.validate_source_target(carrier, capture.profile)
                carrier.pose.bones['Finger'].rotation_mode = 'XYZ'
                try:
                    importer.validate_source_target(carrier, capture.profile)
                except ScoreError:
                    pass
                else:
                    raise AssertionError('Mismatched carrier mode was accepted')
                carrier.pose.bones['Finger'].rotation_mode = 'QUATERNION'
                try:
                    importer.extract_action(binding, source_id='synthetic_batch', sample_fps=1e12)
                except ScoreError:
                    pass
                else:
                    raise AssertionError('Oversized extraction was accepted')
                # Two distinct Actions survive a real .blend round trip and CLI
                # enumeration; scene selection is deliberate in multi-scene files.
                blend = work / 'two_actions.blend'
                scene.collection.objects.unlink(carrier)
                bpy.ops.wm.save_as_mainfile(filepath=str(blend), copy=True)
                scene.collection.objects.link(carrier)
                importer.main(['inspect', str(blend), '--scene', scene.name, '--output', str(work / 'inspect.json')])
                inspected = json.loads((work / 'inspect.json').read_text())
                assert len([b for b in inspected['actions'] if 'SourceThreeBones' in b['armature']]) == 2
                importer.main(['extract', str(blend), '--scene', scene.name, '--source-id', 'synthetic_batch',
                               '--output-dir', str(work / 'batch'), '--sample-fps', '30'])
                index = json.loads((work / 'batch' / 'index.json').read_text())
                assert len(index['captures']) == 2 and not index['failures']
                mesh = skin(carrier, 'Finger', 'SourceCarrierSkin')
                motion = native_motion(capture, 'synthetic_source_action')
                motion_path = work / 'source.motion.json'
                write_rig_motion(motion_path, motion)
                bridge.apply_pose(carrier, capture.profile, motion.player().sample(64))
                expected_mesh = vertices(mesh)
                saved = work / 'native_source_pose.blend'
                bridge.main(['apply', '--armature', carrier.name, '--motion', str(motion_path), '--pip', '64', '--save', str(saved)])
                reopen_mesh(saved, mesh.name, expected_mesh)
                report['source'] = dict(action_count=2, retained_finger=True, source_bones=3,
                                       compact_channels=len(capture.profile.channels), source_samples=31,
                                       duration_seconds=capture.frame_times_seconds[-1],
                                       maximum_world_matrix_error=maximum_error, native_saved_reopened_skin=True)
            # A layered Action can animate an armature and its parent in separate
            # slots. Its fractional overall range must survive extraction.
            with bridge._isolated_scene() as scene:
                rig, actions, _ = fixture()
                parent = bpy.data.objects.new('AnimatedParent', None)
                scene.collection.objects.link(parent)
                rig.parent = parent
                action = actions[0]
                parent.animation_data_create()
                parent.animation_data.action = action
                parent.animation_data.action_slot = action.slots.new(id_type='OBJECT', name=parent.name)
                for frame, y in ((.5, 0.), (31.5, 2.)):
                    parent.location.y = y
                    parent.keyframe_insert(data_path='location', frame=frame)
                bridge.set_action_interpolation(action, 'LINEAR')
                binding = next(b for b in importer.action_bindings(rig, actions)[0] if b.action == action)
                close(binding.first_frame, .5)
                close(binding.last_frame, 31.5)
                layered = importer.extract_action(binding, source_id='layered_fixture', sample_fps=60)
                close(layered.frame_times_seconds[-1], 31 / 30)
                assert len(layered.frames) == 63
                assert 'AnimatedParent' in layered.provenance['action_binding']['bound_objects']
                target_carrier = importer.create_source_armature(layered.profile)
                with importer.activate_action(binding):
                    for index in (0, 31, 62):
                        importer._set_frame(.5 + index / 2)
                        bridge.apply_pose(target_carrier, layered.profile, layered.frames[index])
                        for bone in rig.pose.bones:
                            assert matrix_error(rig.matrix_world @ bone.matrix,
                                                target_carrier.pose.bones[bone.name].matrix) < 3e-5
                parent.animation_data.action = bpy.data.actions.new('Unrelated parent action')
                parent.keyframe_insert(data_path='location', frame=1)
                parent.keyframe_insert(data_path='location', frame=31)
                try:
                    importer.extract_action(binding, source_id='layered_fixture')
                except ScoreError as error:
                    assert 'Animated dependencies' in str(error)
                else:
                    raise AssertionError('An unrelated animated parent was silently mixed into the clip')
                report['layered'] = dict(object_parent_slot=True, fractional_endpoints=[.5, 31.5],
                                         source_samples=63, unrelated_dependency_rejected=True)
            # A generated real Rigify rig exercises rest-axis correction, root
            # scale and FK custom-property setup, including a deformed mesh.
            with bridge._isolated_scene():
                bridge.enable_rigify()
                target = bridge._generate_model(importlib.import_module('rigify.metarigs.Basic.basic_human'), component=False)
                profile = bridge.discover_profile(target, 'Basic.basic_human', kind='metarig')
                setup = [dict(channel_number=c.number, value=1) for c in profile.channels
                         if c.bone == 'upper_arm_parent.L' and c.data_path == '["IK_FK"]']
                mapping = dict(format='dancerudiments.fk-map', schema_version=1,
                               source_type_uri=capture.profile.type_uri, target_profile_sha256=profile.fingerprint,
                               source_reference_object_matrix=importer._matrix_values(reference),
                               source_to_target_rotation=[1, 0, 0, 0], root_translation_scale=.2,
                               bones=[dict(source='Hips', target='root', rotation=False, translation=True),
                                      dict(source='Upper', target='upper_arm_fk.L', rotation=True, translation=False)],
                               setup=setup)
                retargeted = importer.retarget_capture(capture, target, profile, mapping)
                assert 'Finger' in retargeted.provenance['retargeting']['unmapped_source_bones']
                mesh = skin(target, 'DEF-upper_arm.L', 'RetargetedRigifySkin')
                first, last = retargeted.frames[0], retargeted.frames[-1]
                bridge.apply_pose(target, profile, first)
                before = vertices(mesh)
                bridge.apply_pose(target, profile, last)
                after = vertices(mesh)
                root = target.pose.bones['root']
                close(root.location.x, .4)
                close(root.location.y, 0)
                assert math.dist(before[0], after[0]) > .1
                assert math.dist([before[0][0] + .4, *before[0][1:]], after[0]) > .01
                motion = native_motion(retargeted, 'synthetic_rigify_fk')
                motion_path = work / 'retargeted.motion.json'
                write_rig_motion(motion_path, motion)
                saved = work / 'native_retargeted_pose.blend'
                bridge.main(['apply', '--armature', target.name, '--motion', str(motion_path), '--pip', '64', '--save', str(saved)])
                reopen_mesh(saved, mesh.name, after)
                bad_map = dict(mapping, target_profile_sha256='0' * 64)
                try:
                    importer.retarget_capture(capture, target, profile, bad_map)
                except ScoreError:
                    pass
                else:
                    raise AssertionError('Mismatched target fingerprint was accepted')
                report['retarget'] = dict(target='Basic.basic_human', mapped_controls=['root', 'upper_arm_fk.L'],
                                          root_scale=.2, missing_finger_reported=True,
                                          native_saved_reopened_skin=True,
                                          maximum_control_angle_error_radians=retargeted.provenance['retargeting']['maximum_control_angle_error_radians'])
        report['status'] = 'passed'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='.cache/blender-motion-batch')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    run(args.output_dir)
