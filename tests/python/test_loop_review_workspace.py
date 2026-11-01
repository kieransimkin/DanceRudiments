"""Local review workspace trust boundaries and actual source-renderer parity.

Synthetic captures/audio only. The HTTP checks need a permitted loopback socket;
the Node check uses the actual shared Three.js source evaluator without a DOM.
"""
import http.client
import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from copy import deepcopy
from dataclasses import replace
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
import test_loop_review as review_fixtures
from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion_import import RigCapture
from dancerudiments_authoring.rigs import RigChannel
from dancerudiments_authoring.world_motion import evaluate_world_motion
from test_world_motion import portable_capture

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
import build_loop_review_assets as assets
import build_loop_review_test_fixture as browser_fixture
import review_motion_loop as service

selection = review_fixtures.selection
timing = review_fixtures.timing
TARGET = review_fixtures.TARGET
pytestmark = pytest.mark.skipif(importlib.util.find_spec('numpy') is None,
                               reason='optional motion-import NumPy dependency unavailable')


LICENSE = {'id': 'CC0-1.0', 'url': 'https://creativecommons.org/publicdomain/zero/1.0/',
           'attribution': 'Synthetic regression fixture; no artistic approval'}


@pytest.fixture
def workspace(tmp_path, selection, timing):
    """Exercise real finishing/review state with a tiny declared static site."""
    directory, manifest, source = selection
    report, _, audio = timing
    root = tmp_path / 'workspace'
    (root / 'inputs').mkdir(parents=True)
    inputs = {}
    for key, path, name in [('capture', source, 'source.capture.json'),
                            ('calibration', source, 'calibration.capture.json'),
                            ('alignment', report, 'alignment.json')]:
        target = root / 'inputs' / name
        shutil.copyfile(path, target)
        inputs[key] = {'path': 'inputs/' + name, **assets.descriptor(target)}
    shutil.copytree(directory, root / 'selections' / 'initial')
    site = root / 'site'
    site.mkdir()
    payloads = {'index.html': b'<!doctype html><title>Synthetic review</title>',
                'app.js': b'// synthetic site fixture\n',
                'motions/source.json': b'{"private_synthetic_motion":true}',
                'characters/target.bin': b'synthetic local target bytes'}
    inventory = {}
    for relative, raw in payloads.items():
        target = site / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        inventory[relative] = assets.descriptor(target)
    assets.write_json(site / 'build.json', {'files': inventory})
    config = {'format': service.WORKSPACE_FORMAT, 'schema_version': 1, 'scene_id': 'review-action',
        'target': deepcopy(TARGET), 'boundary_range_seconds': [0., 2.], 'review_kind': 'automated_test',
        'original_source_sha256': manifest['source']['original_source_sha256'],
        'repair_options': {'translation_scale': 1.}, 'title': 'Synthetic local workspace',
        'license': LICENSE, 'inputs': inputs,
        'audio': {'path': str(audio), 'mime_type': 'audio/wav', **assets.descriptor(audio)},
        'site': {'build': assets.descriptor(site / 'build.json'), 'files': inventory}}
    assets.write_json(root / 'workspace.json', config)
    assets.write_json(root / 'state.json', {'revision': 1, 'selection_dir': 'selections/initial',
        'timing_revision': None, 'review': None, 'last_review': None, 'draft': {}, 'last_export': None})
    (root / 'reviews').mkdir()
    (root / 'exports').mkdir()
    return service.ReviewWorkspace(root)


def review_body(timing, revision=1):
    return {'expected_revision': revision, 'timing_revision': service.read_review(timing[1]),
        'reviewer': 'Automated synthetic regression', 'review_kind': 'automated_test', 'notes': 'Fixture only',
        'verdicts': {'seam': 'accept', 'feet': 'accept', 'skin': 'accept'}}


def state_bytes(workspace):
    return (workspace.root / 'state.json').read_bytes()


def require_renderer():
    if shutil.which('node') is None or not (ROOT / 'node_modules/three').is_dir():
        if os.environ.get('DANCERUDIMENTS_REQUIRE_REVIEW_UI') == '1':
            pytest.fail('Source renderer parity requires Node and npm ci in the review UI job')
        pytest.skip('Source renderer parity needs Node and npm ci')


@pytest.mark.parametrize('payload', [b'[]', b'{"x":1,"x":2}', b'{"x":NaN}',
                                      b'{"x":Infinity}', b'{"x":1e999}'])
def test_request_json_rejects_duplicate_nonfinite_and_nonobject_documents(payload):
    with pytest.raises((ScoreError, ValueError)):
        service.strict_json(payload)


@pytest.mark.parametrize('relative', ['', '.', '..', '../outside', 'a/../outside',
                                      'a//b', 'a/./b', '/absolute', 'a\\b'])
def test_workspace_paths_do_not_normalize_unsafe_inputs(tmp_path, relative):
    with pytest.raises(ScoreError):
        service.owned(tmp_path, relative)


def test_workspace_paths_reject_symlink_ancestors(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'root'
    root.mkdir()
    try:
        (root / 'alias').symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Symlinks unavailable to this test user')
    with pytest.raises(ScoreError):
        service.owned(root, 'alias/file.json')


def test_stale_draft_cannot_change_selected_clip_or_revision(workspace):
    current = workspace.session()
    changed = workspace.draft({'expected_revision': 1, 'draft': {'notes': 'first writer'}})
    assert changed['revision'] == 2
    before = state_bytes(workspace)
    with pytest.raises(service.StaleRevisionError):
        workspace.draft({'expected_revision': 1, 'draft': {'notes': 'stale writer'}})
    assert state_bytes(workspace) == before
    assert workspace.session()['selection']['selection_id'] == current['selection']['selection_id']
    retry = workspace.draft({'expected_revision': changed['revision'], 'draft': {'notes': 'retry'}})
    assert retry['revision'] == changed['revision'] + 1
    assert (workspace.root / '.review-write-lock').is_file()


def test_failed_finish_preserves_original_selection_and_saved_review(workspace, timing):
    accepted = workspace.review(review_body(timing))
    before = state_bytes(workspace)
    existing = sorted(p.name for p in (workspace.root / 'selections').iterdir())
    with pytest.raises(ScoreError, match='BPM'):
        workspace.finish({'expected_revision': accepted['revision'], 'start_seconds': 0.,
                              'end_seconds': .01, 'beats': 4})
    assert state_bytes(workspace) == before
    assert sorted(p.name for p in (workspace.root / 'selections').iterdir()) == existing
    restored = service.ReviewWorkspace(workspace.root).session()
    assert restored['selection'] == accepted['selection']
    assert restored['review'] == accepted['review']
    assert restored['export_ready']


def test_failed_state_write_preserves_previous_result_and_releases_writer_lock(workspace, monkeypatch):
    before = state_bytes(workspace)
    original = workspace.session()['selection']
    def fail_commit(*args, **kwargs):
        raise OSError('Synthetic atomic commit failure')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'atomic_json', fail_commit)
        with pytest.raises(OSError, match='atomic commit'):
            workspace.draft({'expected_revision': 1, 'draft': {'notes': 'not committed'}})
    assert state_bytes(workspace) == before
    assert workspace.session()['selection'] == original
    restarted = service.ReviewWorkspace(workspace.root)
    assert restarted.draft({'expected_revision': 1, 'draft': {'notes': 'retry'}})['revision'] == 2


def test_successful_boundary_finish_invalidates_review_and_export(workspace, timing):
    accepted = workspace.review(review_body(timing))
    changed = workspace.finish({'expected_revision': accepted['revision'], 'start_seconds': 0.,
                                    'end_seconds': 2., 'beats': 2})
    assert changed['revision'] == accepted['revision'] + 1
    assert changed['selection']['selection_id'] != accepted['selection']['selection_id']
    assert changed['selection']['sample_count'] == 128
    assert changed['review'] is None and not changed['export_ready']
    with pytest.raises(FileNotFoundError):
        workspace.file('package')
    with pytest.raises(ScoreError):
        service.validate_loop_review(workspace.root / workspace._state()['selection_dir'],
            accepted['review'], audio_source_path=workspace.config['audio']['path'], expected_target=TARGET)


def test_existing_unlocked_marker_does_not_block_a_writer(workspace):
    lock = workspace.root / '.review-write-lock'
    lock.write_bytes(b'previous completed writer')
    identity = lock.stat().st_ino
    assert workspace.draft({'expected_revision': 1, 'draft': {}})['revision'] == 2
    assert lock.stat().st_ino == identity and lock.read_bytes() == b'previous completed writer'


def test_process_lifetime_lock_rejects_competing_writer_and_recovers_after_termination(workspace):
    """A dead server cannot leave a marker that permanently locks the result."""
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from review_motion_loop import _writer_lock
with _writer_lock(Path(sys.argv[2])):
    print('LOCK_HELD', flush=True)
    sys.stdin.read(1)
"""
    before = state_bytes(workspace)
    process = subprocess.Popen([sys.executable, '-u', '-c', script, str(TOOLS), str(workspace.root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready = queue.Queue()
    reader = threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True)
    reader.start()
    try:
        assert ready.get(timeout=15).strip() == 'LOCK_HELD'
        lock = workspace.root / '.review-write-lock'
        identity = lock.stat().st_ino
        with pytest.raises(service.StaleRevisionError, match='Another review writer'):
            workspace.draft({'expected_revision': 1, 'draft': {'notes': 'competing writer'}})
        assert state_bytes(workspace) == before and lock.stat().st_ino == identity
        # An abrupt process death runs no Python finally handler. The OS must
        # release its lock without age/PID guesses or deleting the shared file.
        process.kill()
        process.wait(timeout=10)
        assert lock.is_file() and lock.stat().st_ino == identity
        restarted = service.ReviewWorkspace(workspace.root)
        saved = restarted.draft({'expected_revision': 1, 'draft': {'notes': 'recovered after crash'}})
        assert saved['revision'] == 2 and saved['draft']['notes'] == 'recovered after crash'
        assert lock.is_file() and lock.stat().st_ino == identity
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
        reader.join(timeout=5)
        assert not reader.is_alive()


def test_current_review_is_required_for_export_and_draft_invalidates_download(workspace, timing):
    body = {'expected_revision': 1, 'package_id': 'workspace_fixture', 'version': '1.0.0',
                'title': 'Automated synthetic workspace'}
    before = state_bytes(workspace)
    with pytest.raises(ScoreError, match='Save the timing'):
        workspace.export(body)
    assert state_bytes(workspace) == before
    approved = workspace.review(review_body(timing))
    assert approved['review']['human_approved'] is False
    assert approved['review']['status'] == 'automated_test_fixture'
    exported = workspace.export({**body, 'expected_revision': approved['revision']})
    archive, mime = workspace.file('package')
    assert mime == 'application/zip' and assets.digest(archive) == exported['sha256']
    before = state_bytes(workspace)
    folders = sorted(p.name for p in (workspace.root / 'exports').iterdir())
    with pytest.raises((ScoreError, ValueError)):
        workspace.export({**body, 'expected_revision': exported['revision'], 'package_id': '../escape'})
    assert state_bytes(workspace) == before
    assert sorted(p.name for p in (workspace.root / 'exports').iterdir()) == folders
    assert workspace.file('package')[0] == archive
    changed = workspace.draft({'expected_revision': exported['revision'],
                               'draft': {'offset_seconds': .123}})
    assert not changed['export_ready'] and changed['review'] is None
    with pytest.raises(FileNotFoundError):
        workspace.file('package')
    with pytest.raises(ScoreError, match='Save the timing'):
        workspace.export({**body, 'expected_revision': changed['revision']})


def test_changed_audio_bytes_fail_read_and_mutation_without_changing_state(workspace):
    audio = Path(workspace.config['audio']['path'])
    before = state_bytes(workspace)
    raw = audio.read_bytes()
    audio.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    for operation in (workspace.session, lambda: workspace.file('audio'),
                      lambda: workspace.draft({'expected_revision': 1, 'draft': {}})):
        with pytest.raises(ScoreError, match='changed'):
            operation()
    assert state_bytes(workspace) == before


def test_changed_configuration_is_rejected_during_existing_session(workspace):
    path = workspace.root / 'workspace.json'
    config = json.loads(path.read_text())
    config['target']['asset_sha256'] = 'd' * 64
    assets.write_json(path, config)
    with pytest.raises(ScoreError, match='configuration changed'):
        workspace.session()


@pytest.fixture
def prepare_arguments(tmp_path, selection, timing, monkeypatch):
    """Keep real source binding/native finishing; isolate publication from bundling."""
    source = selection[2]
    output = tmp_path / 'prepared_workspace'

    def prepared_assets(capture, destination, **kwargs):
        Path(destination).mkdir(parents=True)
        return {'scene_id': 'review-action', 'target': deepcopy(TARGET),
                'source_seconds_range': [0., 2.]}

    def built_site(command, **kwargs):
        assert command[0] == 'node' and Path(command[1]).name == 'build_loop_review_site.mjs'
        destination = Path(command[command.index('--output-dir') + 1])
        destination.mkdir(parents=True)
        index = destination / 'index.html'
        index.write_bytes(b'<!doctype html><title>Synthetic publication fixture</title>')
        assets.write_json(destination / 'build.json', {'files': {'index.html': assets.descriptor(index)}})
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    monkeypatch.setattr(service, 'prepare_review_assets', prepared_assets)
    monkeypatch.setattr(service.subprocess, 'run', built_site)
    return {'capture': source, 'audio': timing[2], 'alignment_report': timing[0],
            'output': output, 'start_seconds': 0., 'end_seconds': 2., 'beats': 4,
            'original_source_sha256': '1' * 64, 'calibration_capture': source,
            'calibration_seconds': 0., 'license': LICENSE,
            'repair_options': {'translation_scale': 1.}, 'automated_test': True}


def test_prepare_publishes_complete_workspace_without_replacing_a_directory(prepare_arguments, monkeypatch):
    original_replace = os.replace

    def windows_replace(source, destination):
        if Path(source).is_dir() or Path(destination).is_dir():
            raise PermissionError('Windows cannot replace an existing directory')
        return original_replace(source, destination)

    monkeypatch.setattr(os, 'replace', windows_replace)
    result = service.prepare_workspace(**prepare_arguments)
    output = prepare_arguments['output']
    assert Path(result['workspace']) == output
    assert (output / 'inputs/source.capture.json').read_bytes() == prepare_arguments['capture'].read_bytes()
    for folder in ('reviews', 'exports'):
        assert (output / folder).is_dir() and not list((output / folder).iterdir())
    session = service.ReviewWorkspace(output).session()
    assert session['revision'] == 1 and session['selection']['sample_count'] == 256
    assert session['review'] is None and not session['export_ready']
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()}
    with pytest.raises(FileExistsError):
        service.prepare_workspace(**prepare_arguments)
    assert before == {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()}


def test_prepare_publication_failure_keeps_sources_and_removes_partial_workspace(prepare_arguments, monkeypatch):
    output = prepare_arguments['output']
    original_link = os.link
    sources = {name: Path(prepare_arguments[name]).read_bytes()
               for name in ('capture', 'audio', 'alignment_report')}

    def fail_commit_marker(source, destination, **kwargs):
        if Path(destination) == output / 'workspace.json':
            raise OSError('Synthetic workspace publication failure')
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(os, 'link', fail_commit_marker)
    with pytest.raises(OSError, match='Synthetic workspace publication failure'):
        service.prepare_workspace(**prepare_arguments)
    assert not output.exists()
    assert not list(output.parent.glob('.loop-review-*'))
    for name, raw in sources.items():
        assert Path(prepare_arguments[name]).read_bytes() == raw


@pytest.fixture
def http_workspace(workspace):
    server = service.create_server(workspace, token='synthetic_test_capability_' + 'a' * 32)
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    worker.start()
    try:
        yield workspace, server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def request(server, path, *, method='GET', body=None, headers=None, token=False, cookie=None):
    prepared = dict(headers or {})
    if token:
        prepared['X-Loop-Review-Token'] = server.review_token
    if cookie:
        prepared['Cookie'] = cookie
    if isinstance(body, dict):
        body = canonical_json(body).encode('ascii')
    if body is not None:
        prepared.setdefault('Content-Type', 'application/json')
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=prepared)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def session_cookie(server):
    status, headers, raw = request(server, '/api/session', token=True)
    assert status == 200, raw
    value = headers.get('Set-Cookie', '')
    cookies = SimpleCookie()
    cookies.load(value)
    assert len(cookies) == 1 and 'HttpOnly' in value and 'SameSite=Strict' in value
    assert list(cookies) == [f'loop_review_{server.server_port}']
    return '; '.join(f'{name}={item.value}' for name, item in cookies.items())


def test_http_source_media_requires_session_capability_and_audio_ranges_match(http_workspace):
    workspace, server = http_workspace
    for path in ('/api/session', '/api/files/audio', '/motions/source.json', '/characters/target.bin'):
        assert request(server, path)[0] == 403, path
    assert request(server, '/')[0] == 200
    cookie = session_cookie(server)
    for path in ('/motions/source.json', '/characters/target.bin'):
        assert request(server, path, cookie=cookie)[0] == 200
    # The UI verifies audio bytes with an authenticated fetch before constructing
    # its local Blob URL; only renderer-owned static fetches use the cookie.
    assert request(server, '/api/files/audio', cookie=cookie)[0] == 403
    status, headers, raw = request(server, '/api/files/audio', token=True,
                                  headers={'Range': 'bytes=7-24'})
    assert status == 206 and raw == Path(workspace.config['audio']['path']).read_bytes()[7:25]
    assert headers['Content-Range'].startswith('bytes 7-24/')
    assert headers['Cache-Control'] == 'no-store'
    assert headers['Cross-Origin-Resource-Policy'] == 'same-origin'
    status, headers, raw = request(server, '/api/files/audio', method='HEAD', token=True)
    assert status == 200 and raw == b''
    assert int(headers['Content-Length']) == workspace.config['audio']['byte_length']
    assert request(server, '/api/files/audio', token=True, headers={'Range': 'bytes=999999-9999999'})[0] == 416


def test_http_rejects_cross_origin_host_and_cookie_only_writes(http_workspace):
    workspace, server = http_workspace
    cookie = session_cookie(server)
    before = state_bytes(workspace)
    body = {'expected_revision': 1, 'draft': {'notes': 'unaccepted request'}}
    assert request(server, '/api/draft', method='POST', body=body, cookie=cookie)[0] == 403
    for headers in ({'Origin': 'https://unrelated.invalid'}, {'Host': 'unrelated.invalid'}):
        assert request(server, '/api/session', token=True, cookie=cookie, headers=headers)[0] == 403
        assert request(server, '/api/draft', method='POST', body=body, token=True,
                       cookie=cookie, headers=headers)[0] == 403
    assert state_bytes(workspace) == before


def test_http_two_workspaces_keep_port_scoped_static_capabilities(http_workspace, tmp_path):
    workspace, server = http_workspace
    second_root = tmp_path / 'second_workspace'
    shutil.copytree(workspace.root, second_root)
    other = service.create_server(service.ReviewWorkspace(second_root),
                                  token='synthetic_second_capability_' + 'b' * 32)
    worker = threading.Thread(target=other.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    worker.start()
    try:
        first_cookie = session_cookie(server)
        second_cookie = session_cookie(other)
        combined = first_cookie + '; ' + second_cookie
        assert request(server, '/motions/source.json', cookie=second_cookie)[0] == 403
        assert request(other, '/motions/source.json', cookie=first_cookie)[0] == 403
        for active in (server, other):
            assert request(active, '/motions/source.json', cookie=combined)[0] == 200
            assert request(active, '/characters/target.bin', cookie=combined)[0] == 200
            assert request(active, '/api/session', cookie=combined)[0] == 403
        assert request(other, '/api/session', headers={'X-Loop-Review-Token': server.review_token})[0] == 403
        assert workspace.session()['revision'] == service.ReviewWorkspace(second_root).session()['revision'] == 1
    finally:
        other.shutdown()
        other.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_http_bad_envelopes_and_stale_revision_leave_saved_state_untouched(http_workspace):
    workspace, server = http_workspace
    before = state_bytes(workspace)
    for payload in (b'[]', b'{"expected_revision":1,"expected_revision":2,"draft":{}}',
                    b'{"expected_revision":1,"draft":{"offset_seconds":NaN}}'):
        assert request(server, '/api/draft', method='POST', token=True, body=payload)[0] == 400
    assert request(server, '/api/draft', method='POST', token=True, body=b'{}',
                   headers={'Content-Length': str(service.MAX_REQUEST + 1)})[0] == 413
    assert request(server, '/api/draft', method='POST', token=True, body=b'{}',
                   headers={'Content-Type': 'text/plain'})[0] == 415
    assert state_bytes(workspace) == before
    body = {'expected_revision': 1, 'draft': {'notes': 'first writer'}}
    assert request(server, '/api/draft', method='POST', token=True, body=body)[0] == 200
    after = state_bytes(workspace)
    assert request(server, '/api/draft', method='POST', token=True, body=body)[0] == 409
    assert state_bytes(workspace) == after


def test_http_malformed_review_and_deep_json_are_controlled_errors(http_workspace, timing):
    workspace, server = http_workspace
    before = state_bytes(workspace)
    body = review_body(timing)
    body['reviewer'] = []
    assert request(server, '/api/review', method='POST', token=True, body=body)[0] == 400
    deeply_nested = b'{"draft":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'
    assert request(server, '/api/draft', method='POST', token=True, body=deeply_nested)[0] == 400
    assert state_bytes(workspace) == before


def test_http_never_serves_workspace_files_through_traversal(http_workspace):
    _, server = http_workspace
    cookie = session_cookie(server)
    for path in ('/workspace.json', '/state.json', '/inputs/source.capture.json',
                 '/api/files/../../state.json', '/motions/%2e%2e/inputs/source.capture.json',
                 '/%2e%2e/workspace.json'):
        assert request(server, path, token=True, cookie=cookie)[0] == 404, path


def source_fixture():
    """Rotated rest bases, animated signed/nonuniform scales and reversed bone order."""
    import numpy as np
    capture = portable_capture(times=[0., .5, 1.])
    source = capture.profile.source
    source['skeleton'].reverse()
    for i, bone in enumerate(source['skeleton']):
        matrix = np.array(bone['rest_matrix']).reshape(4, 4)
        angle = .37 * (i + 1)
        matrix[:3, :3] = [[np.cos(angle), -np.sin(angle), 0.],
                          [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]]
        bone['rest_matrix'] = matrix.reshape(-1).tolist()
    source['omitted_neutral_groups'] = [item for item in source['omitted_neutral_groups']
        if (item['bone'], item['data_path']) != ('Hips', 'scale')]
    channels = list(capture.profile.channels)
    for axis in range(3):
        number = len(channels) + 1
        channels.append(RigChannel(number, f'scale_{axis}', 'Hips', 'scale', axis,
                                   'unitless', -4., 4., 1.))
    profile = replace(capture.profile, channels=tuple(channels), source_json=canonical_json(source))
    rows = [tuple(row) + ((-1.2, 1.5, .8) if index == 1 else (1., 1., 1.))
            for index, row in enumerate(capture.frames)]
    return RigCapture(profile, capture.frame_times_seconds, tuple(rows), capture.provenance_json)


@pytest.mark.skipif(importlib.util.find_spec('numpy') is None, reason='optional NumPy authoring extra')
def test_prepared_source_scene_matches_canonical_world_matrices_in_actual_renderer():
    import numpy as np
    require_renderer()
    capture = source_fixture()
    before = capture.to_dict()
    rig = assets.portable_scene_rig(capture, capture, calibration_seconds=.5,
        retarget_map={'root_target': 'Hips', 'tip_target': 'Chest'},
        target_keys=['root_target', 'tip_target'], source_sha256='1' * 64,
        calibration_file_sha256='2' * 64)
    script = """
import fs from 'node:fs';
import {sourcePoseEvaluator} from './tools/mesh_demo_assets/kandi-boom.js';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const evaluator=sourcePoseEvaluator(input.rig);
process.stdout.write(JSON.stringify(input.frames.map(row=>evaluator.evaluate(row).map(m=>m.toArray()))));
"""
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
        input=json.dumps({'rig': rig, 'frames': capture.frames}), text=True,
        capture_output=True, check=True)
    actual = np.array(json.loads(result.stdout)).reshape(len(capture.frames), len(rig['joints']), 4, 4)
    actual = actual.transpose(0, 1, 3, 2)  # Three's matrix storage is column-major.
    expected = evaluate_world_motion(capture)
    for index, joint in enumerate(rig['joints']):
        canonical_index = expected.bone_names.index(joint['name'])
        np.testing.assert_allclose(actual[:, index], expected.world_matrices[:, canonical_index], atol=2e-12)
    assert capture.to_dict() == before
    assert rig['calibrationPose']['values'] == list(capture.frames[1])
    assert rig['calibrationPose']['source_capture_sha256'] == '2' * 64


@pytest.mark.skipif(importlib.util.find_spec('numpy') is None, reason='optional NumPy authoring extra')
def test_prepared_source_scene_refuses_guessed_calibration_or_incomplete_bone_map():
    capture = source_fixture()
    settings = {'calibration_seconds': .5, 'retarget_map': {'root_target': 'Hips', 'tip_target': 'Chest'},
        'target_keys': ['root_target', 'tip_target'], 'source_sha256': '1' * 64,
        'calibration_file_sha256': '2' * 64}
    with pytest.raises(ScoreError, match='actual captured frame'):
        assets.portable_scene_rig(capture, capture, **{**settings, 'calibration_seconds': .25})
    with pytest.raises(ScoreError, match='one-to-one'):
        assets.portable_scene_rig(capture, capture, **{**settings,
            'retarget_map': {'root_target': 'Hips', 'tip_target': 'Hips'}})
    with pytest.raises(ScoreError, match='one-to-one'):
        assets.portable_scene_rig(capture, capture, **{**settings, 'retarget_map': {'root_target': 'Hips'}})


@pytest.mark.parametrize('mutation,expected', [
    ('asset_bytes', 'Review asset changed'),
    ('path', 'Unsafe review asset path'),
    ('retarget', 'Retarget implementation changed'),
])
def test_site_builder_rejects_changed_prepared_inputs_without_publishing(tmp_path, mutation, expected):
    require_renderer()
    source, output = tmp_path / 'prepared', tmp_path / 'site'
    source.mkdir()
    item = source / 'source.bin'
    item.write_bytes(b'original synthetic asset')
    inventory = {'format': 'dancerudiments.loop-review-assets.v1',
                 'files': {'source.bin': assets.descriptor(item)}}
    config = {'reviewWorkspace': True, 'scenes': [{'id': 'review-action'}],
              'reviewCalibrationEvidence': {
                  'retarget_implementation_sha256': assets.digest(TOOLS / 'mesh_demo_assets/kandi-boom.js')}}
    if mutation == 'asset_bytes':
        item.write_bytes(b'changed synthetic asset!')
    elif mutation == 'path':
        inventory['files']['../outside.bin'] = inventory['files'].pop('source.bin')
    else:
        config['reviewCalibrationEvidence']['retarget_implementation_sha256'] = '0' * 64
    assets.write_json(source / 'config.json', config)
    assets.write_json(source / 'assets.json', inventory)
    result = subprocess.run(['node', str(TOOLS / 'build_loop_review_site.mjs'),
        '--assets-dir', str(source), '--output-dir', str(output)], cwd=ROOT,
        text=True, capture_output=True, check=False)
    assert result.returncode != 0 and expected in result.stderr
    assert not output.exists()
    assert not list(tmp_path.glob('.loop-review-site-*'))
    assert not (tmp_path / 'outside.bin').exists()


def test_synthetic_browser_fixture_is_deterministic_complete_and_explicitly_unapproved(tmp_path):
    import numpy as np
    require_renderer()
    capture = browser_fixture.synthetic_capture()
    assert capture.to_dict() == browser_fixture.synthetic_capture().to_dict()
    mapping = assets.default_retarget_map()
    world = evaluate_world_motion(capture)
    assert set(world.bone_names) == set(mapping.values())
    np.testing.assert_allclose(capture.frames[0], capture.frames[60], atol=1e-15)
    np.testing.assert_allclose(capture.frames[0], capture.frames[120], atol=1e-15)
    assert capture.provenance['human_approved'] is False
    assert capture.profile.source['fixture_target_layout_sha256'] == assets.digest(
        ROOT / 'harness/kandi-boom/source-rig.json')
    first, second = tmp_path / 'first.wav', tmp_path / 'second.wav'
    browser_fixture.synthetic_audio(first, [.25, 1., 2.5])
    browser_fixture.synthetic_audio(second, [.25, 1., 2.5])
    assert first.read_bytes() == second.read_bytes()
    assert len(first.read_bytes()) == 44 + 16000 * 2 * browser_fixture.AUDIO_DURATION
