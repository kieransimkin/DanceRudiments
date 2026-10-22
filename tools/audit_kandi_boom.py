"""Dependency-free, read-only FBX skeleton and asset audit for Kandi Boom.

Usage: python tools/audit_kandi_boom.py --assets harness/kandi-boom/assets \
         --output harness/kandi-boom/rig-audit.json
"""
import argparse
import hashlib
import json
import pathlib
import struct
import sys

FILES = ('kandi-boom.fbx', 'albedo.png', 'normal.png', 'metallic.png', 'roughness.png')
MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'


def _property(data, position):
    kind = chr(data[position]); position += 1
    scalars = {'Y': ('h', 2), 'C': ('?', 1), 'I': ('i', 4),
               'F': ('f', 4), 'D': ('d', 8), 'L': ('q', 8)}
    if kind in scalars:
        fmt, size = scalars[kind]
        return struct.unpack_from('<' + fmt, data, position)[0], position + size
    if kind in ('S', 'R'):
        length = struct.unpack_from('<I', data, position)[0]; position += 4
        content = data[position:position + length]
        if len(content) != length:
            raise ValueError('truncated FBX property')
        return (content.decode('utf-8', 'replace') if kind == 'S' else None), position + length
    if kind in 'fdilbc':
        count, encoding, byte_length = struct.unpack_from('<III', data, position)
        position += 12
        payload = data[position:position + byte_length]
        if len(payload) != byte_length:
            raise ValueError('truncated FBX array')
        if encoding not in (0, 1):
            raise ValueError('unsupported FBX array encoding')
        # Arrays are not needed for the hierarchy audit; do not inflate potentially
        # very large untrusted mesh arrays.
        return {'array_length': count, 'compressed': bool(encoding)}, position + byte_length
    raise ValueError('unsupported FBX property type ' + repr(kind))


def _nodes(data):
    if not data.startswith(MAGIC):
        raise ValueError('expected binary FBX header')
    version = struct.unpack_from('<I', data, len(MAGIC))[0]
    wide = version >= 7500
    header = 25 if wide else 13
    unpack = '<QQQB' if wide else '<IIIB'
    pos = len(MAGIC) + 4
    objects = []
    connections = []
    stack = [(len(data), '')]
    while pos + header <= len(data):
        while stack and pos >= stack[-1][0]:
            stack.pop()
        if not stack:
            break
        end, prop_count, prop_bytes, name_len = struct.unpack_from(unpack, data, pos)
        if end == 0:
            pos = stack[-1][0] if len(stack) > 1 else len(data)
            continue
        if end <= pos or end > len(data) or name_len > 255:
            raise ValueError('invalid FBX node range')
        name_start = pos + header
        name = data[name_start:name_start + name_len].decode('utf-8', 'replace')
        props_start = name_start + name_len
        props_end = props_start + prop_bytes
        if props_end > end:
            raise ValueError('invalid FBX node properties')
        parent = stack[-1][1]
        if (parent == 'Objects' and name in ('Model', 'Deformer', 'Geometry', 'AnimationStack')) or (parent == 'Connections' and name == 'C'):
            values = []
            cursor = props_start
            for _ in range(min(prop_count, 4)):
                value, cursor = _property(data, cursor)
                values.append(value)
            if parent == 'Objects':
                objects.append({'kind': name, 'id': values[0] if values else None,
                                'name': str(values[1]).split('\x00', 1)[0] if len(values) > 1 else '',
                                'subtype': str(values[2]) if len(values) > 2 else ''})
            else:
                connections.append(values)
        pos = props_end
        if pos < end - header:
            stack.append((end, name))
        else:
            pos = end
    return version, objects, connections


def inspect(assets):
    assets = pathlib.Path(assets)
    records = {}
    for filename in FILES:
        path = assets / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'missing or symlinked asset: {path}')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        records[filename] = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    for filename in FILES[1:]:
        with (assets / filename).open('rb') as handle:
            if handle.read(8) != b'\x89PNG\r\n\x1a\n':
                raise ValueError(f'not a PNG: {filename}')
    version, objects, connections = _nodes((assets / FILES[0]).read_bytes())
    models = [o for o in objects if o['kind'] == 'Model']
    skeleton = [o for o in models if o['subtype'] in ('LimbNode', 'Root')]
    model_ids = {o['id']: o for o in models}
    parent_of = {}
    for edge in connections:
        if len(edge) >= 3 and edge[0] == 'OO' and edge[1] in model_ids and edge[2] in model_ids:
            parent_of[edge[1]] = edge[2]
    bones = [{'fbx_id': o['id'], 'name': o['name'], 'subtype': o['subtype'],
              'parent_fbx_id': parent_of.get(o['id']),
              'parent_name': model_ids[parent_of[o['id']]]['name'] if o['id'] in parent_of else None}
             for o in skeleton]
    skins = [o for o in objects if o['kind'] == 'Deformer' and o['subtype'] in ('Skin', 'Cluster')]
    report = {'schema': 'dancerudiments.kandi-boom.rig-audit/v1',
              'character': 'Kandi Boom', 'series': 'Bass Ben & Friends',
              'fbx_version': version, 'assets': records,
              'mesh_count': sum(o['kind'] == 'Geometry' and o['subtype'] == 'Mesh' for o in objects),
              'model_count': len(models), 'bone_count': len(bones),
              'skin_deformer_count': sum(o['subtype'] == 'Skin' for o in skins),
              'cluster_count': sum(o['subtype'] == 'Cluster' for o in skins),
              'animation_stack_count': sum(o['kind'] == 'AnimationStack' for o in objects),
              'bones': bones,
              'rigify_compatible': None,
              'rigify_note': 'Not inferred from FBX names; verify control semantics and rest transforms explicitly.',
              'motion_mapping_status': 'unmapped'}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=pathlib.Path, default=pathlib.Path('harness/kandi-boom/assets'))
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = inspect(args.assets)
        payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding='utf-8')
        else:
            print(payload, end='')
        if not result['bones']:
            print('WARNING: no FBX LimbNode/Root objects found; rig mapping must be blocked', file=sys.stderr)
    except (ValueError, OSError, struct.error) as exc:
        parser.exit(1, f'Kandi Boom asset audit failed: {exc}\n')


if __name__ == '__main__':
    main()
