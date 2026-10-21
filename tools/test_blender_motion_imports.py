#!/usr/bin/env python3
"""Exercise real BVH, FBX and glTF importers with synthetic local motion.

Run in a dedicated headless Blender/official bpy process. No assets, libraries,
model weights or music are downloaded. Scratch files are isolated beneath the
chosen output directory and removed after the test; report.json is retained.
This tests interchange and capture timing, not automatic Rigify retargeting.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from dancerudiments_authoring import blender_bridge as bridge


def _close(actual, expected, tolerance=1e-5):
    if not math.isfinite(actual) or abs(actual - expected) > tolerance:
        raise AssertionError(f'{actual!r} != {expected!r} within {tolerance}')


def _available(bpy, name):
    namespace, operator = name.split('.')
    try:
        getattr(getattr(bpy.ops, namespace), operator).get_rna_type()
    except (AttributeError, RuntimeError):
        return False
    return True


def _write_bvh(path):
    # Original three-frame, 60 Hz motion: a translating root and fixed child.
    path.write_text('''HIERARCHY
ROOT Hips
{
 OFFSET 0 0 0
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT Chest
 {
  OFFSET 0 1 0
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site
  {
   OFFSET 0 1 0
  }
 }
}
MOTION
Frames: 3
Frame Time: 0.016666666666666666
0 0 0 0 0 0 0 0 0
1 0 0 30 0 0 0 0 0
2 0 0 60 0 0 0 0 0
''', encoding='ascii')


def _export_synthetic(bpy, directory):
    """Create our own skinned triangle and one-second, 30 Hz root motion."""
    paths = [directory / 'synthetic.fbx', directory / 'synthetic.glb']
    with bridge._isolated_scene() as scene:
        scene.render.fps, scene.render.fps_base = 30, 1
        scene.frame_start, scene.frame_end = 1, 31
        bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
        rig = bpy.context.object
        rig.name = 'SyntheticImportRig'
        bone = rig.pose.bones[0]
        bone.name = 'Hips'
        bone.rotation_mode = 'QUATERNION'
        old_interpolation = bpy.context.preferences.edit.keyframe_new_interpolation_type
        try:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
            for frame, displacement, angle in ((1, 0, 0), (16, 1, math.pi / 4), (31, 2, math.pi / 2)):
                bone.location = (displacement, 0, 0)
                bone.rotation_quaternion = (math.cos(angle / 2), 0, 0, math.sin(angle / 2))
                bone.keyframe_insert(data_path='location', frame=frame)
                bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        finally:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = old_interpolation
        mesh = bpy.data.meshes.new('SyntheticImportTriangle')
        mesh.from_pydata([(0, 0, 0.5), (0.1, 0, 0.5), (0, 0.1, 0.5)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new('SyntheticImportMesh', mesh)
        scene.collection.objects.link(obj)
        obj.vertex_groups.new(name=bone.name).add([0, 1, 2], 1, 'REPLACE')
        obj.modifiers.new('SyntheticSkin', 'ARMATURE').object = rig
        obj.parent = rig
        scene.frame_set(1)
        for item in scene.objects:
            item.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.fbx(filepath=str(paths[0]), use_selection=True,
                                bake_anim=True, bake_anim_use_all_actions=False,
                                bake_anim_use_nla_strips=False, add_leaf_bones=False)
        bpy.ops.export_scene.gltf(filepath=str(paths[1]), export_format='GLB',
                                 use_selection=True, use_active_scene=True,
                                 export_animations=True, export_animation_mode='ACTIVE_ACTIONS')
        for path in paths:
            if not path.is_file() or path.stat().st_size == 0:
                raise AssertionError(f'Exporter did not write {path.name}')
    return paths


def _import_case(bpy, source, expected_duration, source_fps):
    with bridge._isolated_scene() as scene:
        scene.render.fps, scene.render.fps_base = 24, 1
        destination = source.with_name(source.stem + source.suffix.replace('.', '_') + '.blend')
        bridge.main(['import-source', str(source), '--save', str(destination)])
        if not destination.is_file():
            raise AssertionError('The import-source command did not save its Blender scene')
        armatures = [obj for obj in scene.objects if obj.type == 'ARMATURE'
                     and obj.animation_data and obj.animation_data.action]
        if len(armatures) != 1:
            raise AssertionError(f'Expected one animated armature, found {len(armatures)}')
        rig = armatures[0]
        first, last = rig.animation_data.action.frame_range
        fps = scene.render.fps / scene.render.fps_base
        duration = (last - first) / fps
        _close(duration, expected_duration)
        if source.suffix == '.bvh':
            # Regress the loss of 60 Hz input keys in a default 24 Hz scene.
            _close(fps, 60)
            _close(first, 1)
            _close(last, 3)
        elif source.suffix == '.fbx' and _available(bpy, 'wm.fbx_import'):
            _close(fps, source_fps)
        if source.suffix != '.bvh':
            skinned = [obj for obj in scene.objects if obj.type == 'MESH'
                       and any(mod.type == 'ARMATURE' and mod.object == rig for mod in obj.modifiers)]
            if not skinned:
                raise AssertionError('Import lost the mesh-to-armature binding')
        # glTF times can become fractional frames. Capture the actual endpoints
        # at the chosen 30 Hz sampling rate; do not round away source phase.
        profile = bridge.discover_profile(rig, 'synthetic.import_check', kind='custom')
        scene.frame_set(7, subframe=0.25)
        capture = bridge.capture_action(rig, profile, first, last, frame_step=fps / source_fps)
        index = next(i for i, channel in enumerate(profile.channels)
                     if channel.binding == ('Hips', 'location', 0))
        values = [row[index] for row in capture.frames]
        _close(capture.frame_times_seconds[0], 0)
        _close(capture.frame_times_seconds[-1], expected_duration)
        _close(values[0], 0)
        _close(values[-1], 2)
        _close(values[len(values) // 2], 1)
        _close(scene.frame_current, 7)
        _close(scene.frame_subframe, 0.25)
        if len(capture.frames) != round(expected_duration * source_fps) + 1:
            raise AssertionError('Capture lost an endpoint or an expected source sample')
        return dict(format=source.suffix[1:], scene_fps=fps,
                    action_frame_range=[first, last], duration_seconds=duration,
                    capture_samples=len(capture.frames), capture_sample_fps=source_fps,
                    capture_origin_seconds=capture.frame_times_seconds[0],
                    capture_end_seconds=capture.frame_times_seconds[-1],
                    root_x_first_mid_last=[values[0], values[len(values) // 2], values[-1]],
                    saved_blend=True, status='passed')


def run(output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Probe the exact runtime/output parent before importer/exporter work.
    with tempfile.TemporaryDirectory(prefix='preflight-', dir=output) as directory:
        original = Path(directory) / 'original'
        original.write_text('probe', encoding='ascii')
        assert original.read_text(encoding='ascii') == 'probe'
        renamed = original.with_name('renamed')
        original.rename(renamed)
        assert renamed.read_text(encoding='ascii') == 'probe'
        renamed.unlink()
    import bpy
    report = dict(blender_version=bpy.app.version_string,
                  blender_build_hash=bpy.app.build_hash.decode('ascii'),
                  source='original synthetic motion and skinned triangle; no external assets',
                  cases=[], status='failed')
    try:
        report['operators'] = {name: _available(bpy, name) for name in (
            'wm.fbx_import', 'import_scene.fbx', 'export_scene.fbx',
            'import_anim.bvh', 'import_scene.gltf', 'export_scene.gltf')}
        with tempfile.TemporaryDirectory(prefix='imports-', dir=output) as directory:
            work = Path(directory)
            bvh = work / 'synthetic_60fps.bvh'
            _write_bvh(bvh)
            report['cases'].append(_import_case(bpy, bvh, 2 / 60, 60))
            fbx, glb = _export_synthetic(bpy, work)
            report['cases'].append(_import_case(bpy, fbx, 1, 30))
            report['cases'].append(_import_case(bpy, glb, 1, 30))
        report['status'] = 'passed'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, help='Report and temporary-fixture parent directory')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    run(args.output_dir)
