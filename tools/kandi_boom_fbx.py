"""Bounded, dependency-free inspection of Kandi Boom's binary FBX source.

This validates source data, *not* Three.js/Blender runtime playback or Rigify
compatibility. It intentionally does not generate animation channels or retarget
motion. Untrusted array payloads have decompression and allocation limits.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import struct
import zlib

MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'
MAX_FILE = 256 * 1024 * 1024
MAX_ARRAY_BYTES = 64 * 1024 * 1024
MAX_PROPERTIES = 200000
MAX_NODES = 1000000


@dataclass(frozen=True)
class FbxArray:
    kind: str
    count: int
    encoded: bytes
    compression: int

    def values(self):
        formats = {'f': 'f', 'd': 'd', 'i': 'i', 'l': 'q', 'b': 'b', 'c': 'b'}
        width = struct.calcsize(formats[self.kind])
        size = self.count * width
        if size > MAX_ARRAY_BYTES:
            raise ValueError('FBX array exceeds permitted decoded size')
        if self.compression == 1:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(self.encoded, size + 1)
            if (len(raw) != size or not decoder.eof or decoder.unused_data
                    or decoder.unconsumed_tail):
                raise ValueError('invalid or overlong compressed FBX array')
        else:
            raw = self.encoded
            if len(raw) != size:
                raise ValueError('incorrect uncompressed FBX array size')
        return struct.unpack('<' + str(self.count) + formats[self.kind], raw)


@dataclass
class FbxNode:
    name: str
    props: list
    children: list

    def child(self, name):
        return next((c for c in self.children if c.name == name), None)

    def children_named(self, name):
        return [c for c in self.children if c.name == name]


def parse_fbx(data):
    """Decode supported FBX 7.x binary nodes with exact record boundaries."""
    if not data.startswith(MAGIC) or len(data) < 40:
        raise ValueError('expected binary FBX header')
    if len(data) > MAX_FILE:
        raise ValueError('FBX exceeds permitted file size')
    version = struct.unpack_from('<I', data, len(MAGIC))[0]
    if not 7100 <= version < 8000:
        raise ValueError(f'unsupported FBX version {version}')
    wide = version >= 7500
    header_size = 25 if wide else 13
    header_format = '<QQQB' if wide else '<IIIB'
    node_counter = 0

    def property_at(offset, limit):
        if offset >= limit:
            raise ValueError('truncated FBX property')
        kind = chr(data[offset])
        offset += 1
        scalar = {'Y': 'h', 'C': '?', 'I': 'i', 'F': 'f', 'D': 'd', 'L': 'q'}
        if kind in scalar:
            size = struct.calcsize(scalar[kind])
            if offset + size > limit:
                raise ValueError('truncated FBX scalar')
            return struct.unpack_from('<' + scalar[kind], data, offset)[0], offset + size
        if kind in ('S', 'R'):
            if offset + 4 > limit:
                raise ValueError('truncated FBX string header')
            size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if offset + size > limit:
                raise ValueError('truncated FBX string')
            blob = data[offset:offset + size]
            return (blob.decode('utf-8', errors='replace') if kind == 'S' else blob), offset + size
        if kind in 'fdilbc':
            if offset + 12 > limit:
                raise ValueError('truncated FBX array header')
            count, compression, byte_size = struct.unpack_from('<III', data, offset)
            offset += 12
            if compression not in (0, 1) or offset + byte_size > limit:
                raise ValueError('unsupported or truncated FBX array')
            width = {'f': 4, 'd': 8, 'i': 4, 'l': 8, 'b': 1, 'c': 1}[kind]
            if count * width > MAX_ARRAY_BYTES:
                raise ValueError('FBX array exceeds permitted decoded size')
            return FbxArray(kind, count, data[offset:offset + byte_size], compression), offset + byte_size
        raise ValueError(f'unsupported FBX property kind {kind!r}')

    def sequence(start, bound, depth=0):
        nonlocal node_counter
        if depth > 64:
            raise ValueError('FBX hierarchy exceeds safe depth')
        result = []
        offset = start
        while offset + header_size <= bound:
            end_offset, count, property_bytes, name_length = struct.unpack_from(
                header_format, data, offset)
            if end_offset == 0 and count == 0 and property_bytes == 0 and name_length == 0:
                return result, offset + header_size
            if (end_offset <= offset or end_offset > bound or
                    count > MAX_PROPERTIES or node_counter >= MAX_NODES):
                raise ValueError('invalid FBX node offset, property count or node count')
            node_counter += 1
            first = offset + header_size
            property_start = first + name_length
            property_end = property_start + property_bytes
            if property_end > end_offset:
                raise ValueError('FBX properties exceed node bounds')
            name = data[first:property_start].decode('utf-8', errors='replace')
            props = []
            cursor = property_start
            for _ in range(count):
                prop, cursor = property_at(cursor, property_end)
                props.append(prop)
            if cursor != property_end:
                raise ValueError('FBX property length mismatch')
            children = []
            if property_end < end_offset - header_size:
                children, child_end = sequence(property_end, end_offset, depth + 1)
                if child_end != end_offset:
                    raise ValueError('FBX child record offset mismatch')
            elif property_end != end_offset and property_end != end_offset - header_size:
                raise ValueError('invalid FBX node terminator')
            result.append(FbxNode(name, props, children))
            offset = end_offset
        return result, offset

    nodes, _ = sequence(len(MAGIC) + 4, len(data))
    return version, nodes


def _array(node, name, required=True):
    child = node.child(name)
    if child is None:
        if required:
            raise ValueError(f'{node.name} missing {name}')
        return ()
    if len(child.props) != 1 or not isinstance(child.props[0], FbxArray):
        raise ValueError(f'{node.name}.{name} is not an FBX array')
    return child.props[0].values()


def _ident(node):
    return str(node.props[1]).split('\x00', 1)[0]


def _finite(values, label):
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f'{label} contains non-finite numbers')


def _matrix(node, label):
    values = _array(node, label)
    if len(values) != 16:
        raise ValueError(f'{node.name}.{label}: expected 4x4 matrix')
    _finite(values, label)
    if max(abs(v - x) for v, x in zip((values[3], values[7], values[11], values[15]),
                                      (0, 0, 0, 1))) > .0002:
        raise ValueError(f'{node.name}.{label}: invalid homogeneous matrix')
    return values


def _matmul_error(a, b):
    # FBX row-major arrays use translation in entries 12..14. Identity check
    # works identically with row- or column-vector conventions, as long as both
    # operands follow the same convention.
    return max(abs(sum(a[4 * i + k] * b[4 * k + j] for k in range(4)) -
                   (1 if i == j else 0)) for i in range(4) for j in range(4))


def _norm_error(coords):
    if len(coords) % 3:
        raise ValueError('normal coordinates must be XYZ triples')
    _finite(coords, 'normals')
    return max((abs(math.sqrt(sum(coords[i + j] ** 2 for j in range(3))) - 1)
                for i in range(0, len(coords), 3)), default=0)


def _prop70_values(model, key):
    properties = model.child('Properties70')
    if properties:
        for p in properties.children_named('P'):
            if p.props and p.props[0] == key:
                vals = p.props[4:]
                if vals and all(isinstance(x, (int, float)) for x in vals):
                    _finite(vals, f'model {key}')
                return vals
    return []


def inspect_fbx(data, asset_hash):
    """Return source report + raw pose manifest; raise on invalid source assets.

    Not a production FBX importer: Blender or another full importer still needs
    to confirm bind-space conventions and render/deformation behaviour.
    """
    version, nodes = parse_fbx(data)
    objects = next((n for n in nodes if n.name == 'Objects'), None)
    connections = next((n for n in nodes if n.name == 'Connections'), None)
    if objects is None or connections is None:
        raise ValueError('FBX has no objects or connections')
    object_by_id = {}
    for node in objects.children:
        if node.props and isinstance(node.props[0], int):
            if node.props[0] in object_by_id:
                raise ValueError('duplicate FBX object id')
            object_by_id[node.props[0]] = node
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for conn in connections.children_named('C'):
        if len(conn.props) < 3 or conn.props[0] not in ('OO', 'OP'):
            raise ValueError('malformed FBX connection')
        _, source, target = conn.props[:3]
        if source not in object_by_id or (target != 0 and target not in object_by_id):
            raise ValueError('FBX connection references missing object')
        if conn.props[0] == 'OO':
            outgoing[source].append(target)
            incoming[target].append(source)
    models = {oid: n for oid, n in object_by_id.items() if n.name == 'Model'}
    bones = {oid: n for oid, n in models.items() if n.props[2] in ('LimbNode', 'Root')}
    if not bones:
        raise ValueError('FBX contains no skeleton')
    names = [_ident(b) for b in bones.values()]
    if len(set(names)) != len(names):
        raise ValueError('duplicate bone names')
    for oid in bones:
        par = [p for p in outgoing[oid] if p in models]
        if len(par) != 1:
            raise ValueError(f'bone {_ident(bones[oid])} must have exactly one model parent')
        seen = {oid}
        at = oid
        while True:
            chain = [p for p in outgoing[at] if p in models]
            if not chain:
                break
            at = chain[0]
            if at in seen:
                raise ValueError('cyclic model hierarchy')
            seen.add(at)

    geometries = [n for n in object_by_id.values() if n.name == 'Geometry' and n.props[2] == 'Mesh']
    if len(geometries) != 1:
        raise ValueError('expected one skinned mesh geometry')
    geo = geometries[0]
    verts = _array(geo, 'Vertices')
    if not verts or len(verts) % 3:
        raise ValueError('invalid mesh vertex array')
    _finite(verts, 'vertices')
    vertex_count = len(verts) // 3
    corners = _array(geo, 'PolygonVertexIndex')
    if not corners:
        raise ValueError('mesh has no polygons')
    polygon_sizes = []
    poly_size = 0
    for packed in corners:
        idx = -packed - 1 if packed < 0 else packed
        if idx < 0 or idx >= vertex_count:
            raise ValueError('polygon vertex index outside mesh')
        poly_size += 1
        if packed < 0:
            if poly_size < 3:
                raise ValueError('degenerate polygon')
            polygon_sizes.append(poly_size)
            poly_size = 0
    if poly_size:
        raise ValueError('unfinished FBX polygon')
    normals = geo.child('LayerElementNormal')
    uv = geo.child('LayerElementUV')
    materials = geo.child('LayerElementMaterial')
    if normals is None or uv is None or materials is None:
        raise ValueError('mesh missing normals, UVs or material layer')
    normal_mapping = normals.child('MappingInformationType').props[0]
    normal_reference = normals.child('ReferenceInformationType').props[0]
    normal_values = _array(normals, 'Normals')
    normal_count = len(normal_values) // 3
    if (normal_mapping, normal_reference) != ('ByPolygonVertex', 'Direct') or normal_count != len(corners):
        raise ValueError('unexpected or inconsistent normal mapping')
    norm_deviation = _norm_error(normal_values)
    if norm_deviation > .005:
        raise ValueError('mesh normals not normalised')
    uv_mapping = uv.child('MappingInformationType').props[0]
    uv_reference = uv.child('ReferenceInformationType').props[0]
    uv_data = _array(uv, 'UV')
    uv_indices = _array(uv, 'UVIndex')
    if (uv_mapping, uv_reference) != ('ByPolygonVertex', 'IndexToDirect') or len(uv_data) % 2:
        raise ValueError('unexpected UV mapping')
    _finite(uv_data, 'UV coordinates')
    if len(uv_indices) != len(corners) or min(uv_indices) < 0 or max(uv_indices) >= len(uv_data) // 2:
        raise ValueError('UV corner index outside coordinates')
    mat_values = _array(materials, 'Materials')
    if (materials.child('MappingInformationType').props[0] != 'AllSame'
            or len(mat_values) != 1 or mat_values[0] != 0):
        raise ValueError('unexpected material assignment')

    skins = {oid: n for oid, n in object_by_id.items() if n.name == 'Deformer' and n.props[2] == 'Skin'}
    clusters = {oid: n for oid, n in object_by_id.items() if n.name == 'Deformer' and n.props[2] == 'Cluster'}
    if len(skins) != 1:
        raise ValueError('expected exactly one skin deformer')
    skin_id = next(iter(skins))
    if outgoing[skin_id] != [geo.props[0]]:
        raise ValueError('skin is not linked to expected mesh geometry')

    poses = [n for n in object_by_id.values() if n.name == 'Pose' and n.props[2] == 'BindPose']
    if len(poses) != 1:
        raise ValueError('expected one explicit BindPose')
    pose = poses[0]
    pose_map = {}
    for pn in pose.children_named('PoseNode'):
        node = pn.child('Node')
        matrix = pn.child('Matrix')
        if node is None or matrix is None or len(node.props) != 1:
            raise ValueError('incomplete bind pose entry')
        bone_id = node.props[0]
        if bone_id in pose_map:
            raise ValueError('duplicate bind pose object id')
        pose_map[bone_id] = _matrix(pn, 'Matrix')
    if set(bones) - set(pose_map):
        raise ValueError('bind pose missing skeleton joints')
    if len(pose_map) != len(pose.children_named('PoseNode')):
        raise ValueError('bind pose node count mismatch')

    weights_per_vertex = [[] for _ in range(vertex_count)]
    bone_skin_counts = {}
    max_inverse_error = 0.0
    max_pose_error = 0.0
    inverse_binds = {}
    bone_cluster_ids = {}
    for cluster_id, cluster in clusters.items():
        if outgoing[cluster_id] != [skin_id]:
            raise ValueError('cluster not attached to expected skin')
        sources = [oid for oid in incoming[cluster_id] if oid in bones]
        if len(sources) != 1:
            raise ValueError('cluster must have precisely one linked skeleton bone')
        bone_id = sources[0]
        if bone_id in bone_skin_counts:
            raise ValueError('multiple clusters affect same bone')
        links = _matrix(cluster, 'TransformLink')
        inv = _matrix(cluster, 'Transform')
        associated = _matrix(cluster, 'TransformAssociateModel')
        # Source-specific Blender FBX exporter writes inverse bind in Transform,
        # global rest pose in TransformLink, and root armature in AssociateModel.
        # Validate their algebra; do not infer a generic FBX interpretation.
        max_inverse_error = max(max_inverse_error, _matmul_error(inv, links), _matmul_error(links, inv))
        max_pose_error = max(max_pose_error, max(abs(a - b) for a, b in zip(links, pose_map[bone_id])))
        if max(abs(a - b) for a, b in zip(associated, pose_map[next(
                oid for oid, obj in models.items() if _ident(obj) == 'Armature')])) > .0003:
            raise ValueError('cluster associates to different armature transform')
        indices = _array(cluster, 'Indexes', required=False)
        values = _array(cluster, 'Weights', required=False)
        if len(indices) != len(values):
            raise ValueError('skin cluster indexes and weights differ in length')
        for idx, weight in zip(indices, values):
            if not 0 <= idx < vertex_count:
                raise ValueError('skin index outside geometry vertex count')
            if not math.isfinite(weight) or not 0 < weight <= 1.00001:
                raise ValueError('invalid or nonpositive skin influence')
            weights_per_vertex[idx].append((bone_id, weight))
        inverse_binds[bone_id] = tuple(inv)
        bone_skin_counts[bone_id] = len(indices)
        bone_cluster_ids[bone_id] = cluster_id
    if set(bone_skin_counts) != set(bones):
        raise ValueError('skeleton is not completely covered by clusters')
    if max_pose_error > 1e-5 or max_inverse_error > .0002:
        raise ValueError('bind/link/pose matrices are inconsistent')
    if any(not entries for entries in weights_per_vertex):
        raise ValueError('one or more mesh control points have no skin influence')
    sums = [sum(w for _, w in entries) for entries in weights_per_vertex]
    max_sum_error = max(abs(s - 1) for s in sums)
    if max_sum_error > .0001:
        raise ValueError('skin weights do not sum to unity')
    truncated = [sum(sorted((w for _, w in entry), reverse=True)[4:])
                 for entry in weights_per_vertex if len(entry) > 4]
    count_large = sum(x > .01 for x in truncated)
    mesh_bounds = [[float(min(verts[dim::3])), float(max(verts[dim::3]))]
                   for dim in range(3)]
    if any(lo > hi for lo, hi in mesh_bounds):
        raise ValueError('invalid mesh bounds')

    curves = [n for n in object_by_id.values() if n.name == 'AnimationCurve']
    stacks = [n for n in object_by_id.values() if n.name == 'AnimationStack']
    curve_lengths = []
    times = set()
    for curve in curves:
        key_times = _array(curve, 'KeyTime')
        key_values = _array(curve, 'KeyValueFloat')
        if len(key_times) != len(key_values):
            raise ValueError('animation times and values differ in length')
        if tuple(sorted(key_times)) != key_times:
            raise ValueError('animation key times not ordered')
        _finite(key_values, 'animation curve')
        times.update(key_times)
        curve_lengths.append(len(key_times))
    varying = sum(length > 1 for length in curve_lengths)

    settings = next((n for n in nodes if n.name == 'GlobalSettings'), None)
    if not settings:
        raise ValueError('missing FBX global settings')
    globals70 = settings.child('Properties70')
    global_values = {p.props[0]: p.props[4] for p in globals70.children_named('P') if len(p.props) >= 5}
    axes = {'up': global_values.get('UpAxis'), 'front': global_values.get('FrontAxis'),
            'coord': global_values.get('CoordAxis')}
    if sorted(axes.values()) != [0, 1, 2]:
        raise ValueError('ambiguous FBX global axes')
    unit_scale = global_values.get('UnitScaleFactor')
    if not isinstance(unit_scale, (int, float)) or not math.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError('invalid FBX unit scale')

    named_bones = []
    for bone_id, bone in bones.items():
        parent_models = [p for p in outgoing[bone_id] if p in models]
        parent = parent_models[0] if parent_models else None
        named_bones.append({
            'fbx_id': bone_id, 'name': _ident(bone),
            'parent_fbx_id': parent,
            'parent_name': _ident(models[parent]) if parent is not None else None,
            'source_local_translation': _prop70_values(bone, 'Lcl Translation'),
            'source_local_rotation_degrees': _prop70_values(bone, 'Lcl Rotation'),
            'source_local_scale': _prop70_values(bone, 'Lcl Scaling'),
            'world_bind_matrix': [float(v) for v in pose_map[bone_id]],
            'inverse_bind_matrix': [float(v) for v in inverse_binds[bone_id]],
            'cluster_fbx_id': bone_cluster_ids[bone_id],
            'influenced_control_points': bone_skin_counts[bone_id],
        })

    source_rig = {
        'schema': 'dancerudiments.source-rig/v1',
        'type_uri': 'syn://type/danceflow/motion/rig/custom/kandi-boom',
        'name': 'Kandi Boom', 'series': 'Bass Ben & Friends',
        'fbx_asset_sha256': asset_hash,
        'source_skeleton': 'FBX LimbNode; not a verified Blender Rigify control rig',
        'coordinate_system': {'up_axis': axes['up'], 'front_axis': axes['front'],
                              'coord_axis': axes['coord'],
                              'up_sign': global_values.get('UpAxisSign'),
                              'front_sign': global_values.get('FrontAxisSign'),
                              'coord_sign': global_values.get('CoordAxisSign'),
                              'unit_scale_factor': unit_scale},
        'rest_pose_only': True,
        'channel_mapping_status': 'unmapped',
        'bones': named_bones,
    }
    canonical = json.dumps(source_rig, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    source_rig['fingerprint_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    # Warning-based gates are deliberate: source assets are internally valid,
    # while animation usability and 4-influence runtime compatibility are not.
    report = {
        'schema': 'dancerudiments.kandi-boom.deep-audit/v1',
        'fbx_version': version,
        'mesh': {
            'name': _ident(geo), 'control_point_count': vertex_count,
            'polygon_count': len(polygon_sizes), 'triangle_count': sum(n - 2 for n in polygon_sizes),
            'triangle_only': all(n == 3 for n in polygon_sizes),
            'polygon_corner_count': len(corners),
            'bounds_xyz_in_fbx_units': mesh_bounds,
            'normal_count': normal_count, 'max_normal_length_deviation': norm_deviation,
            'uv_count': len(uv_data) // 2, 'uv_index_count': len(uv_indices),
            'uv_range': [min(uv_data), max(uv_data)],
            'uv_mapping': uv_mapping, 'uv_reference': uv_reference,
            'material_slot_count': 1,
        },
        'skin': {
            'deformer_count': len(skins), 'cluster_count': len(clusters),
            'influenced_cluster_count': sum(bool(x) for x in bone_skin_counts.values()),
            'zero_influence_bones': [_ident(bones[oid]) for oid, c in bone_skin_counts.items() if c == 0],
            'vertex_count': vertex_count, 'unweighted_vertex_count': 0,
            'max_influences_per_vertex': max(len(e) for e in weights_per_vertex),
            'influence_count_histogram': {str(k): v for k, v in sorted(Counter(len(e) for e in weights_per_vertex).items())},
            'vertices_with_over_four_influences': len(truncated),
            'vertices_discarding_over_one_percent_at_four': count_large,
            'max_discarded_weight_if_four_influences': max(truncated, default=0),
            'mean_discarded_weight_on_over_four_vertices': sum(truncated) / len(truncated) if truncated else 0,
            'maximum_weight_sum_error': max_sum_error,
        },
        'bind_pose': {
            'pose_object_count': len(poses), 'pose_matrix_count': len(pose_map),
            'bone_count': len(bones), 'max_cluster_link_pose_error': max_pose_error,
            'max_inverse_bind_identity_error': max_inverse_error,
        },
        'animation': {
            'stack_count': len(stacks), 'curve_count': len(curves),
            'curve_key_count_histogram': {str(k): v for k, v in sorted(Counter(curve_lengths).items())},
            'unique_animation_ticks': sorted(times),
            'time_varying_curve_count': varying,
            'contains_recorded_motion': varying > 0,
        },
        'coordinate_system': source_rig['coordinate_system'],
        'source_rig_fingerprint_sha256': source_rig['fingerprint_sha256'],
        'source_integrity_valid': True,
        'production_four_influence_ready': not truncated,
        'motion_retargeting_complete': False,
        'browser_render_validated': False,
        'notes': [
            'Skin cluster Transform is inverse of TransformLink for this source; do not generalize to all FBX exporters.',
            'The supplied PBR maps are external; original FBX material primarily refers to embedded base colour.',
            'More than four influences require an 8+ influence skinning path or controlled weight reduction before export.'
        ]
    }
    return report, source_rig
