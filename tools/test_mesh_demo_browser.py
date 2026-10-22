#!/usr/bin/env python3
"""Verify the actual lazy-loaded, native-WASM skinned mesh gallery in Chromium.

Reference poses come from separately compiled Python-native recordings and
independent NumPy joint transforms. The browser always uses production playback.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import partial
import gzip
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import threading
from urllib.parse import urljoin, urlsplit

from package_release_pages import file_identity, preflight, safe_relative, site_files, write_json


def asset(root, relative):
    candidate = root / safe_relative(relative)
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(root) or not candidate.is_file():
        raise ValueError(f'Invalid local gallery asset: {relative}')
    return candidate


def hashed_json(root, relative, expected_hash):
    candidate = asset(root, relative)
    if file_identity(candidate, relative)['sha256'] != expected_hash:
        raise ValueError(f'Local reference integrity differs: {relative}')
    return json.loads(candidate.read_text(encoding='utf-8'))


def maximum_error(actual, expected):
    if len(actual) != len(expected):
        raise AssertionError('Reference array width differs')
    differences = []
    for left, right in zip(actual, expected):
        if isinstance(right, list):
            differences.append(maximum_error(left, right))
        else:
            if not isinstance(left, (int, float)) or not math.isfinite(left):
                raise AssertionError('Browser returned a non-finite physical value')
            differences.append(abs(left - right))
    return max(differences, default=0.)


@contextmanager
def local_server(root):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test(site_dir, output_dir, prefix=None, chromium=None, gallery_only=False, base_url=None):
    from playwright.sync_api import sync_playwright

    site = Path(site_dir).resolve()
    mesh = site / 'meshes'
    output = Path(output_dir).resolve()
    if output == site or output.is_relative_to(site):
        raise ValueError('Browser evidence must be outside the site until it is sealed')
    build = json.loads((mesh / 'build.json').read_text(encoding='utf-8'))
    catalogue = json.loads((mesh / 'catalogue.json').read_text(encoding='utf-8'))
    if (build.get('format') != 'dancerudiments.mesh-demo-build' or build.get('schema_version') != 1
            or catalogue.get('format') != 'dancerudiments.mesh-demo-catalogue'
            or catalogue.get('schema_version') != 1 or len(catalogue.get('scenes', [])) != 2
            or {scene.get('id') for scene in catalogue['scenes']} != {'boxbot', 'prism'}):
        raise ValueError('Expected the built two-scene mesh gallery')
    prefix = prefix or f'DanceRudiments-mesh-demos-v{build["version"]}'
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', prefix):
        raise ValueError('Browser artifact prefix must be a safe filename')
    preflight(output)
    inputs = [file_identity(p, p.relative_to(site).as_posix()) for p in site_files(site)
              if p not in (site / 'site-manifest.json', mesh / 'validation.json')]
    checks, errors, blocked, requests, scenes = [], [], [], [], []
    report = dict(format='dancerudiments.mesh-demo-browser-verification', schema_version=1,
                  status='FAIL', scope='mesh-gallery-only' if gallery_only else 'complete-site',
                  version=build['version'], source_commit=build['commit'], tested_assets=inputs,
                  scenes=scenes, checks=checks, screenshots=[],
                  source_timing='time-only; musical BPM and phase unverified',
                  rendering='Chromium WebGL 2; ANGLE SwiftShader software renderer')

    def check(condition, description):
        if not condition:
            raise AssertionError(description)
        checks.append(description)
        print(description, flush=True)

    if not gallery_only:
        visualizer = json.loads((site / 'index.json').read_text(encoding='utf-8'))
        check(visualizer['version'] == build['version'] and visualizer['source_commit'] == build['commit'],
              'The root visualizer and mesh gallery share the exact release identity')
        check(file_identity(site / 'index.html', 'index.html')['sha256'] == visualizer['html_sha256'],
              'Prepared root visualizer matches its HTML manifest')
        html = (site / 'index.html').read_text(encoding='utf-8')
        check('id="mesh-demos-link" href="meshes/"' in html,
              'The existing root visualizer links to the separate mesh route')
        report['visualizer_source_kind'] = visualizer.get('source_kind', 'unspecified')

    references = {}
    recordings = {}
    for scene in catalogue['scenes']:
        reference = hashed_json(mesh, scene['browserReferencePath'], scene['browserReferenceSha256'])
        check(reference['sceneId'] == scene['id'] and reference['matrixLayout'] == 'row-major',
              f'{scene["id"]}: independent source/native pose reference is identified')
        check(reference['sourceSha256'] == scene['sourceSha256']
              and reference['sceneRigSha256'] == scene['sceneRigSha256']
              and reference['manifestSha256'] == scene['manifestSha256'],
              f'{scene["id"]}: reference binds the original capture, rig and package')
        manifest = hashed_json(mesh, scene['manifestPath'], scene['manifestSha256'])
        base = Path(scene['manifestPath']).parent
        data = {}
        for descriptor in manifest['clips']:
            path = asset(mesh, (base / descriptor['path']).as_posix())
            identity = file_identity(path, descriptor['path'])
            check(identity['sha256'] == descriptor['sha256'] and identity['byte_length'] == descriptor['byte_length'],
                  f'{scene["id"]}: packaged recording integrity is valid')
            payload = path.read_bytes()
            if descriptor['encoding'] == 'gzip':
                payload = gzip.decompress(payload)
            check(len(payload) == descriptor['decoded_byte_length'],
                  f'{scene["id"]}: independent gzip decoder preserves declared recording bytes')
            data[descriptor['id']] = json.loads(payload)
        references[scene['id']] = reference
        recordings[scene['id']] = data

    def exercise(url):
        origin = urlsplit(url)
        expected_origin = (origin.scheme, origin.netloc)
        with sync_playwright() as pw:
            options = dict(headless=True, args=['--no-sandbox', '--mute-audio', '--disable-dev-shm-usage',
                '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            if chromium:
                options['executable_path'] = str(Path(chromium).resolve())
            browser = pw.chromium.launch(**options)
            report['browser_version'] = browser.version
            context = browser.new_context(viewport=dict(width=1440, height=1000),
                device_scale_factor=1, reduced_motion='reduce', service_workers='block')
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            def restrict(route):
                target = urlsplit(route.request.url)
                if target.scheme in ('http', 'https') and (target.scheme, target.netloc) != expected_origin:
                    blocked.append(route.request.url)
                    route.abort()
                else:
                    requests.append(target.path)
                    route.continue_()
            page.route('**/*', restrict)
            page.goto(urljoin(url, 'meshes/'), wait_until='networkidle', timeout=60000)
            page.wait_for_function('Boolean(window.meshDemo?.debugSnapshot)', timeout=30000)
            snapshot = lambda: page.evaluate('meshDemo.debugSnapshot()')
            initial = snapshot()
            check(initial['error'] is None, 'WebGL stage initialized without a browser error')
            check(page.evaluate('Boolean(document.getElementById("stage").getContext("webgl2"))'),
                  'The actual renderer owns a WebGL 2 context')
            check(initial['activeNativeHandles'] == 0 and initial['skinnedMeshCount'] == 0,
                  'Initial navigation allocates no character or native motion handle')
            check(not any('/motions/' in value or value.endswith('.wasm') for value in requests),
                  'Initial navigation fetches no rig, profile, recording or WASM payload')
            check(not initial['playing'], 'Motion does not play before the user loads a character')

            def seek(pip):
                page.locator('#seek').evaluate('(input,pip)=>{input.value=String(pip);input.dispatchEvent(new Event("input",{bubbles:true}));}', pip)
                page.wait_for_function('(pip)=>meshDemo.debugSnapshot().currentPip===pip && meshDemo.debugSnapshot().pendingRequests===0', arg=pip)
                return snapshot()

            for index, scene in enumerate(catalogue['scenes']):
                sid = scene['id']
                before = snapshot()
                selection_start = len(requests)
                page.locator(f'[data-scene="{sid}"]').click()
                page.wait_for_function('(id)=>{const s=meshDemo.debugSnapshot();return s.selectedSceneId===id&&s.disposed&&s.activeNativeHandles===0&&s.skinnedMeshCount===0&&s.pendingRequests===0;}', arg=sid)
                page.wait_for_load_state('networkidle')
                if index:
                    unloaded = snapshot()
                    check(unloaded['disposedNativeHandles'] > before['disposedNativeHandles']
                          and unloaded['disposedGeometries'] > before['disposedGeometries'],
                          'Switching characters disposes the previous native handle and skin geometry')
                    scenes[-1]['unloaded_by_scene_switch'] = True
                check(not any(f'/motions/{sid}/' in value for value in requests[selection_start:]),
                      f'{sid}: selecting the card does not load its motion')
                request_start = len(requests)
                page.locator('#load-scene').click()
                page.wait_for_function('(id)=>{const s=meshDemo.debugSnapshot();return s.ready&&s.sceneId===id&&s.pendingRequests===0;}', arg=sid, timeout=60000)
                state = snapshot()
                check(state['error'] is None and state['activeNativeHandles'] == 1,
                      f'{sid}: user load creates exactly one native recording handle')
                check(not state['playing'], f'{sid}: reduced-motion preference preserves explicit paused inspection')
                check(state['skinnedMeshCount'] >= 1 and state['vertexCount'] > 0
                      and state['weightedVertexCount'] == state['vertexCount'] and state['blendedVertexCount'] > 0,
                      f'{sid}: actual skinned geometry contains vertices with multiple bone weights')
                other = {item['id'] for item in catalogue['scenes']} - {sid}
                check(not any(f'/motions/{name}/' in request for name in other for request in requests[request_start:]),
                      f'{sid}: load fetches only the selected character package')
                check(not any(value.endswith('browser-reference.json') for value in requests),
                      f'{sid}: playback does not fetch the independent QA reference')
                reference = references[sid]
                check(state['jointNames'] == reference['jointNames'], f'{sid}: all source joints retain their hierarchy order')
                pose_checks, vertices = [], []
                for expected in reference['samples']:
                    state = seek(expected['pip'])
                    clip = recordings[sid][expected['clipId']]
                    row = clip['samples'][expected['pip'] - clip['clock']['start_pip']]
                    normalized_error = maximum_error(state['nativeNormalizedSample'], row)
                    physical_error = maximum_error(state['physicalSample'], expected['physicalValues'])
                    matrix_error = maximum_error(state['jointWorldMatrices'], expected['jointWorldMatrices'])
                    check(state['loadedChunkId'] == expected['clipId'] and normalized_error == 0,
                          f'{sid}: pip {expected["pip"]} matches every independently decoded normalized channel')
                    check(physical_error <= reference['tolerances']['physicalAbsolute'],
                          f'{sid}: pip {expected["pip"]} matches Python-native physical channels')
                    check(matrix_error <= reference['tolerances']['worldMatrixAbsolute'],
                          f'{sid}: pip {expected["pip"]} matches independent source-space joint matrices')
                    vertices.append(state['representativeDeformedVertices'])
                    pose_checks.append(dict(pip=expected['pip'], normalized_max_error=normalized_error,
                        physical_max_error=physical_error, world_matrix_max_error=matrix_error))
                deformation = max(maximum_error(frame, vertices[0]) for frame in vertices[1:])
                check(deformation > 1e-5, f'{sid}: real skinned vertex positions change across the captured dance')
                first = scene['startPip']
                seek(first)
                calls = snapshot()['nativeSampleCalls']
                page.locator('#play-toggle').click()
                page.wait_for_function('(first)=>meshDemo.debugSnapshot().currentPip>first+2', arg=first)
                page.locator('#play-toggle').click()
                page.wait_for_function('!meshDemo.debugSnapshot().playing && meshDemo.debugSnapshot().pendingRequests===0')
                # The transport pauses immediately; its final integer pip is
                # applied by the existing animation frame, then stays fixed.
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                frozen = snapshot()
                page.wait_for_timeout(100)
                check(snapshot()['currentPip'] == frozen['currentPip'] and not snapshot()['playing'],
                      f'{sid}: pause freezes the integer-pip pose')
                check(snapshot()['nativeSampleCalls'] > calls, f'{sid}: playback calls the existing native WASM sampler')
                page.locator('#speed').select_option('2')
                check(snapshot()['currentPip'] == frozen['currentPip'], f'{sid}: changing preview speed preserves paused position')
                seek(scene['endPip'] - 4)
                page.locator('#play-toggle').click()
                page.wait_for_function('(last)=>{const s=meshDemo.debugSnapshot();return s.currentPip===last&&!s.playing;}', arg=scene['endPip'])
                check(snapshot()['currentPip'] == scene['endPip'], f'{sid}: the complete non-looping action stops at its final recorded pip')
                page.locator('#restart').click()
                page.wait_for_function('(last)=>meshDemo.debugSnapshot().currentPip<last', arg=scene['endPip'])
                page.locator('#play-toggle').click()
                page.locator('#speed').select_option('1')
                display_pip = reference['samples'][2]['pip']
                seek(display_pip)
                page.locator('#reset-view').click()
                for label, width, height in (('desktop', 1440, 1000), ('mobile', 390, 844)):
                    page.set_viewport_size(dict(width=width, height=height))
                    page.evaluate('window.scrollTo(0,0)')
                    page.wait_for_timeout(180)
                    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),
                          f'{sid}: {label} layout fits the viewport')
                    check(page.locator('#stage').bounding_box()['width'] > 100,
                          f'{sid}: {label} layout keeps the real character canvas visible')
                    name = f'{prefix}-{sid}-{label}.png'
                    page.screenshot(path=str(output / name), full_page=True)
                    report['screenshots'].append(name)
                page.set_viewport_size(dict(width=1440, height=1000))
                scenes.append(dict(id=sid, source_sha256=scene['sourceSha256'], profile_sha256=scene['expectedProfile']['fingerprint'],
                    start_pip=scene['startPip'], end_pip=scene['endPip'], sample_count=scene['sampleCount'],
                    vertex_count=state['vertexCount'], weighted_vertex_count=state['weightedVertexCount'],
                    blended_vertex_count=state['blendedVertexCount'], bone_count=state['boneCount'],
                    skinned_mesh_count=state['skinnedMeshCount'], pose_checks=pose_checks,
                    skinned_vertex_max_change=deformation, lazy_selected_package_only=True,
                    real_native_playback_verified=True))
            before = snapshot()
            page.locator('#unload-scene').click()
            page.wait_for_function('meshDemo.debugSnapshot().activeNativeHandles===0 && meshDemo.debugSnapshot().pendingRequests===0')
            unloaded = snapshot()
            check(unloaded['skinnedMeshCount'] == 0 and unloaded['loadedCacheIds'] == []
                  and unloaded['disposedNativeHandles'] > before['disposedNativeHandles']
                  and unloaded['disposedGeometries'] > before['disposedGeometries'],
                  'Explicit unload releases character geometry, scoped motion cache and native handles')
            check(page.locator('#play-toggle').is_disabled() and page.locator('#seek').is_disabled(),
                  'Unloaded native recordings cannot be sampled through the controls')
            scenes[-1]['explicit_unload_verified'] = True
            check(not errors, 'No unhandled browser exceptions')
            check(not blocked, 'The gallery uses only same-origin bundled assets')
            report['network_paths'] = sorted(set(requests))
            report['initial_eager_motion_requests'] = 0
            report['native_handles_after_unload'] = unloaded['activeNativeHandles']
            browser.close()

    try:
        if base_url:
            exercise(base_url.rstrip('/') + '/')
        else:
            with local_server(site) as url:
                exercise(url)
        report['status'] = 'PASS'
    except BaseException as error:
        report['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        write_json(output / f'{prefix}-browser.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, default=Path('dist/pages'))
    parser.add_argument('--output-dir', type=Path, default=Path('dist/demo'))
    parser.add_argument('--prefix')
    parser.add_argument('--chromium', type=Path)
    parser.add_argument('--gallery-only', action='store_true', help='Inspect only /meshes/ locally; this receipt cannot seal a release site')
    parser.add_argument('--url', help='Optionally inspect an already deployed base URL against the same local expected files')
    args = parser.parse_args(argv)
    report = test(args.site_dir, args.output_dir, args.prefix, args.chromium, args.gallery_only, args.url)
    print(f'{len(report["checks"])} browser checks passed; {len(report["scenes"])} real skinned characters verified')


if __name__ == '__main__':
    main()
