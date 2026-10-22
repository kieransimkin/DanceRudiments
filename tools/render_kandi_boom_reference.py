"""Optional source-mesh rest/pose render for Kandi Boom asset QA.

Requires numpy + VTK (not required by the DanceRudiments base package).
This is an independent source-data preview, *not* an FBXLoader/WebGL or PBR
reference; browser rendering must be verified separately. Uses row-vector FBX
matrices and a simple 25-degree shoulder-controlled arm raise.

python tools/render_kandi_boom_reference.py --output-dir generated/kandi-qa
"""
import argparse
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from kandi_boom_fbx import _array, parse_fbx  # noqa: E402


def source_skin_vertices(vertices, objects, manifest, degrees=25):
    """Linear-blend-skin a controlled raised-arm pose and validate rest identity."""
    import numpy as np
    bone_by_id = {b['fbx_id']: b for b in manifest['bones']}
    clusters = [obj for obj in objects if obj.name == 'Deformer' and obj.props[2] == 'Cluster']
    clusters_by_id = {obj.props[0]: obj for obj in clusters}
    raw = np.column_stack([vertices, np.ones(len(vertices), dtype='float64')])
    rest = np.zeros_like(vertices, dtype='float64')
    posed = np.zeros_like(vertices, dtype='float64')
    weights = np.zeros(len(vertices), dtype='float64')

    def delta_for(side):
        import math
        anchor = next(b for b in manifest['bones'] if b['name'] == side + 'Arm')
        px, py, pz = anchor['world_bind_matrix'][12:15]
        angle = math.radians(degrees) * (1 if side == 'Left' else -1)
        c, s = math.cos(angle), math.sin(angle)
        t0 = np.eye(4);t0[3, :3] = (-px, -py, -pz)
        t1 = np.eye(4);t1[3, :3] = (px, py, pz)
        r = np.eye(4);r[0, :2] = (c, s);r[1, :2] = (-s, c)
        return t0 @ r @ t1

    left, right = delta_for('Left'), delta_for('Right')
    for bone in manifest['bones']:
        cluster = clusters_by_id[bone['cluster_fbx_id']]
        idx = np.asarray(_array(cluster, 'Indexes', required=False), dtype='int64')
        w = np.asarray(_array(cluster, 'Weights', required=False), dtype='float64')
        if len(idx) == 0:
            continue
        inv = np.asarray(bone['inverse_bind_matrix'], dtype='float64').reshape(4, 4)
        bind = np.asarray(bone['world_bind_matrix'], dtype='float64').reshape(4, 4)
        name = bone['name']
        motion = (left if name in ('LeftArm', 'LeftForeArm', 'LeftHand') else
                  right if name in ('RightArm', 'RightForeArm', 'RightHand') else np.eye(4))
        # All rows of the source mesh are already in source-global space.
        rest[idx] += (raw[idx] @ inv @ bind)[:, :3] * w[:, None]
        posed[idx] += (raw[idx] @ inv @ bind @ motion)[:, :3] * w[:, None]
        weights[idx] += w
    if not np.allclose(weights, 1, atol=.0001):
        raise ValueError('skin weights do not reconstruct to unity')
    max_rest_error = float(np.max(np.abs(rest - vertices)))
    if max_rest_error > .005:
        raise ValueError(f'inverse bind matrices fail rest-pose reconstruction: {max_rest_error}')
    displaced = np.linalg.norm(posed - rest, axis=1)
    if int((displaced > .01).sum()) < 100:
        raise ValueError('controlled arm pose did not move enough weighted vertices')
    return rest, posed, {'max_rest_vertex_error_in_fbx_units': max_rest_error,
                        'moved_vertex_count': int((displaced > .01).sum()),
                        'max_vertex_displacement_in_fbx_units': float(displaced.max())}


def draw(vertices, corners, uv_corner, normals, albedo, output):
    """Render a simple albedo-only full-body preview using VTK offscreen."""
    import numpy as np
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    corner_ix = np.where(corners < 0, -corners - 1, corners)
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(vertices[corner_ix].astype('float32'), deep=True))
    mesh = vtk.vtkPolyData()
    mesh.SetPoints(points)
    # Triangular source mesh, one corner vertex for each UV/normal assignment.
    offsets = np.arange(0, len(corners) + 1, 3, dtype=np.int64)
    indices = np.arange(len(corners), dtype=np.int64)
    polys = vtk.vtkCellArray()
    polys.SetData(numpy_to_vtk(offsets, deep=True, array_type=vtk.VTK_ID_TYPE),
                  numpy_to_vtk(indices, deep=True, array_type=vtk.VTK_ID_TYPE))
    mesh.SetPolys(polys)
    mesh.GetPointData().SetTCoords(numpy_to_vtk(uv_corner.astype('float32'), deep=True))
    mesh.GetPointData().SetNormals(numpy_to_vtk(normals.astype('float32'), deep=True))
    mapper = vtk.vtkPolyDataMapper();mapper.SetInputData(mesh)
    actor = vtk.vtkActor();actor.SetMapper(mapper)
    reader = vtk.vtkPNGReader();reader.SetFileName(str(albedo));reader.Update()
    texture = vtk.vtkTexture();texture.SetInputConnection(reader.GetOutputPort());texture.InterpolateOn()
    actor.SetTexture(texture)
    scene = vtk.vtkRenderer();scene.SetBackground(.05, .03, .09);scene.AddActor(actor)
    light = vtk.vtkLight();light.SetLightTypeToSceneLight();light.SetPosition(100, 200, 300)
    light.SetFocalPoint(0, 90, 0);light.SetIntensity(1.6);scene.AddLight(light)
    cam = scene.GetActiveCamera();cam.SetPosition(0, 86, 330);cam.SetFocalPoint(0, 87, 0)
    cam.SetViewUp(0, 1, 0);cam.ParallelProjectionOn();cam.SetParallelScale(102)
    window = vtk.vtkRenderWindow();window.OffScreenRenderingOn();window.AddRenderer(scene)
    window.SetSize(650, 800);window.Render()
    capture = vtk.vtkWindowToImageFilter();capture.SetInput(window);capture.Update()
    writer = vtk.vtkPNGWriter();writer.SetInputConnection(capture.GetOutputPort())
    writer.SetFileName(str(output));writer.Write()
    window.Finalize()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=pathlib.Path, default=pathlib.Path('harness/kandi-boom/assets'))
    parser.add_argument('--source-rig', type=pathlib.Path, default=pathlib.Path('harness/kandi-boom/source-rig.json'))
    parser.add_argument('--output-dir', type=pathlib.Path, default=pathlib.Path('generated/kandi-boom-qa'))
    args = parser.parse_args()
    import hashlib
    import json
    import numpy as np
    manifest = json.loads(args.source_rig.read_text(encoding='utf-8'))
    binary = (args.assets / 'kandi-boom.fbx').read_bytes()
    if hashlib.sha256(binary).hexdigest() != manifest['fbx_asset_sha256']:
        raise ValueError('FBX does not match source rig profile')
    _, root = parse_fbx(binary)
    all_objects = next(x for x in root if x.name == 'Objects').children
    geo = next(x for x in all_objects if x.name == 'Geometry' and x.props[2] == 'Mesh')
    vertices = np.asarray(_array(geo, 'Vertices'), dtype='float64').reshape(-1, 3)
    corners = np.asarray(_array(geo, 'PolygonVertexIndex'), dtype='int32')
    uv = geo.child('LayerElementUV')
    uv_corner = np.asarray(_array(uv, 'UV'), dtype='float64').reshape(-1, 2)[
        np.asarray(_array(uv, 'UVIndex'), dtype='int64')]
    normals = np.asarray(_array(geo.child('LayerElementNormal'), 'Normals'),
                         dtype='float64').reshape(-1, 3)
    rest, posed, results = source_skin_vertices(vertices, all_objects, manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    draw(rest, corners, uv_corner, normals, args.assets / 'albedo.png', args.output_dir / 'kandi-rest.png')
    draw(posed, corners, uv_corner, normals, args.assets / 'albedo.png', args.output_dir / 'kandi-arms-raised.png')
    (args.output_dir / 'render-report.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
