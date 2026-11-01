#!/usr/bin/env python3
"""Prepare and serve a local imported-Action review, finishing and export workspace.

This source-checkout tool reuses the canonical authoring backend, Kandi renderer,
StemLab timing revisions and native recording sampler. It never downloads media.
"""
from __future__ import annotations

import argparse
import errno
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
sys.path.insert(0, str(ROOT/'tools'))

from build_loop_review_assets import (
    descriptor,
    digest,
    prepare_review_assets,
    write_json,
)
from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.loop_review import (
    _new_directory,
    create_loop_review,
    export_reviewed_loop,
    finish_review_selection,
    load_selection,
    read_review,
    validate_loop_review,
    write_review,
)
from dancerudiments_authoring.motion_packages import export_motion_package

WORKSPACE_FORMAT = 'dancerudiments.loop-review-workspace.v1'
MAX_REQUEST = 2 * 1024 * 1024
MAX_AUDIO = 256 * 1024 * 1024
_HASH = re.compile(r'^[a-f0-9]{64}$')


class StaleRevisionError(ScoreError):
    pass


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ScoreError('Duplicate JSON key: '+key)
            result[key] = value
        return result
    def bad(value):
        raise ScoreError('Nonfinite JSON value: '+value)
    try:
        result = json.loads(data, object_pairs_hook=pairs, parse_constant=bad)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ScoreError('Invalid or excessively nested JSON') from exc
    if not isinstance(result, dict):
        raise ScoreError('Expected a JSON object')
    try:
        canonical_json(result)
    except RecursionError as exc:
        raise ScoreError('Excessively nested review JSON') from exc
    return result


def owned(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ScoreError('Invalid workspace asset path')
    root = Path(root).resolve()
    path = root.joinpath(*relative.split('/'))
    if not path.resolve().is_relative_to(root):
        raise ScoreError('Workspace path escapes its root')
    cursor = root
    for part in relative.split('/'):
        cursor /= part
        if cursor.is_symlink():
            raise ScoreError('Workspace assets cannot be symlinks')
    return path


def checked(path, expected, *, limit=None):
    path = Path(path)
    size = path.stat().st_size
    if (not path.is_file() or path.is_symlink() or size < 1
            or limit is not None and size > limit
            or size != expected['byte_length'] or digest(path) != expected['sha256']):
        raise ScoreError('A saved workspace source or asset changed; prepare a new workspace')
    return path


def atomic_json(path, value):
    path = Path(path)
    raw = (canonical_json(value)+'\n').encode('ascii')
    fd, temporary = tempfile.mkstemp(prefix='.review-state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def preflight(parent):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.review-probe-', dir=parent) as folder:
        before, after = Path(folder)/'before', Path(folder)/'after'
        before.write_bytes(b'loop-review')
        if before.read_bytes() != b'loop-review':
            raise OSError('Temporary-directory read failed')
        before.rename(after)
        after.unlink()


@contextmanager
def _writer_lock(root):
    """An OS-held lock releases on process exit; an old marker never blocks work.

    Keep the lock file in place after unlocking. Unlinking it would let another
    process lock a new inode while a waiter still owns the old one.
    """
    path = owned(root, '.review-write-lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    locked = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ScoreError('The review writer lock must be a regular file')
        if os.name == 'nt':
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'\0')
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                raise StaleRevisionError('Another review writer is active; reload after it finishes') from exc
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise StaleRevisionError('Another review writer is active; reload after it finishes') from exc
        locked = True
        yield
    finally:
        try:
            if locked:
                if os.name == 'nt':
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _input(path, maximum):
    path = Path(path).resolve()
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= maximum:
        raise ScoreError('Input is missing, not a regular file, or exceeds its size limit')
    return path


def prepare_workspace(*, capture, audio, alignment_report, output, start_seconds,
                      end_seconds, beats, original_source_sha256, calibration_capture,
                      calibration_seconds, license, retarget_map=None,
                      repair_options=None, title='Imported Action loop review',
                      automated_test=False):
    """Prepare an immutable source/site snapshot and the first unapproved loop."""
    from stemlab.analysis.motion_alignment import read_document

    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if not isinstance(original_source_sha256, str) or not _HASH.fullmatch(original_source_sha256):
        raise ScoreError('The exact original media SHA-256 is required')
    if not isinstance(license, dict) or any(not isinstance(license.get(k), str) or not license[k].strip()
                                          for k in ('id', 'url', 'attribution')):
        raise ScoreError('Supply source licence id, url and attribution explicitly')
    capture = _input(capture, 64*1024*1024)
    calibration_capture = _input(calibration_capture, 64*1024*1024)
    audio = _input(audio, MAX_AUDIO)
    alignment_report = _input(alignment_report, MAX_REQUEST*16)
    report, _ = read_document(alignment_report)
    if (report.get('format') != 'stemlab.motion-alignment.v1'
            or report.get('motion_source', {}).get('sha256') != digest(capture)
            or report.get('audio_source', {}).get('sha256') != digest(audio)):
        raise ScoreError('Alignment report must bind these exact original capture and audio bytes')
    preflight(output.parent)
    with _new_directory(output, commit_files=('workspace.json',)) as temporary:
        inputs = temporary/'inputs'
        inputs.mkdir()
        for source, filename in [(capture, 'source.capture.json'), (calibration_capture, 'calibration.capture.json'),
                                 (alignment_report, 'alignment.json')]:
            shutil.copyfile(source, inputs/filename)
        selection_dir = temporary/'selections'/'initial'
        selection = finish_review_selection(inputs/'source.capture.json', selection_dir,
            start_seconds=start_seconds, end_seconds=end_seconds, beats=beats,
            original_source_sha256=original_source_sha256, repair_options=repair_options,
            verify_native=True)
        prepared = prepare_review_assets(inputs/'source.capture.json', temporary/'assets',
            start_seconds=start_seconds, end_seconds=end_seconds,
            original_source_sha256=original_source_sha256,
            calibration_capture_path=inputs/'calibration.capture.json',
            calibration_seconds=calibration_seconds, license=license,
            retarget_map=retarget_map, title=title)
        try:
            subprocess.run(['node', str(ROOT/'tools/build_loop_review_site.mjs'),
                '--assets-dir', str(temporary/'assets'), '--output-dir', str(temporary/'site')],
                cwd=ROOT, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise ScoreError('Review-site build failed: '+exc.stderr.strip()[-4000:]) from exc
        site_receipt = strict_json((temporary/'site/build.json').read_bytes())
        config = {'format': WORKSPACE_FORMAT, 'schema_version': 1, 'scene_id': prepared['scene_id'],
            'target': prepared['target'], 'boundary_range_seconds': prepared['source_seconds_range'],
            'review_kind': 'automated_test' if automated_test else 'human',
            'original_source_sha256': original_source_sha256, 'repair_options': repair_options or {},
            'title': title, 'license': license,
            'inputs': {name: dict(path=f'inputs/{filename}', **descriptor(inputs/filename)) for name, filename in [
                ('capture','source.capture.json'), ('calibration','calibration.capture.json'), ('alignment','alignment.json')]},
            'audio': dict(path=str(audio), mime_type=mimetypes.guess_type(audio.name)[0] or 'application/octet-stream',
                       **descriptor(audio)),
            'site': {'build': descriptor(temporary/'site/build.json'), 'files': site_receipt['files']}}
        write_json(temporary/'workspace.json', config)
        write_json(temporary/'state.json', {'revision': 1, 'selection_dir': 'selections/initial',
            'timing_revision': None, 'review': None, 'last_review': None, 'draft': {}, 'last_export': None})
        (temporary/'reviews').mkdir()
        (temporary/'exports').mkdir()
        # The prepared renderer input is not a served/downloadable artefact.
        shutil.rmtree(temporary/'assets')
    return {'workspace': str(output), 'selection_id': selection['selection_id'],
            'review_kind': config['review_kind'], 'target': prepared['target']}


class ReviewWorkspace:
    """File-backed state with optimistic revisions and immutable source evidence."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = strict_json((self.root/'workspace.json').read_bytes())
        if self.config.get('format') != WORKSPACE_FORMAT or self.config.get('schema_version') != 1:
            raise ScoreError('Unknown loop-review workspace')
        self._config_sha = digest(self.root/'workspace.json')
        self.lock = threading.RLock()
        self._verify_inputs(include_site=True)

    def _verify_inputs(self, *, include_site=False):
        if digest(self.root/'workspace.json') != self._config_sha:
            raise ScoreError('Workspace configuration changed during review')
        for item in self.config['inputs'].values():
            checked(owned(self.root, item['path']), item, limit=64*1024*1024)
        checked(Path(self.config['audio']['path']), self.config['audio'], limit=MAX_AUDIO)
        checked(self.root/'site/build.json', self.config['site']['build'])
        if include_site:
            for name, info in self.config['site']['files'].items():
                checked(owned(self.root/'site', name), info, limit=64*1024*1024)

    def _state(self):
        state = strict_json((self.root/'state.json').read_bytes())
        if type(state.get('revision')) is not int or state['revision'] < 1:
            raise ScoreError('Invalid saved workspace revision')
        return state

    @contextmanager
    def _mutation(self, expected):
        with self.lock, _writer_lock(self.root):
            state = self._state()
            if type(expected) is not int or expected != state['revision']:
                raise StaleRevisionError('This workspace changed in another tab; reload before saving')
            self._verify_inputs(include_site=True)
            yield state
            state['revision'] += 1
            atomic_json(self.root/'state.json', state)

    def _path(self, name):
        return owned(self.root, name)

    def session(self):
        from stemlab.analysis.motion_alignment import document_hash as timing_hash
        from stemlab.analysis.motion_alignment import read_document

        with self.lock:
            self._verify_inputs(include_site=True)
            state = self._state()
            selection = load_selection(self._path(state['selection_dir']))
            report, report_sha = read_document(self._path(self.config['inputs']['alignment']['path']))
            timing = read_review(self._path(state['timing_revision'])) if state['timing_revision'] else None
            review = read_review(self._path(state['review'])) if state['review'] else None
            ready = False
            if review:
                validate_loop_review(self._path(state['selection_dir']), review,
                    audio_source_path=self.config['audio']['path'], expected_target=self.config['target'])
                ready = bool(review['human_approved'] or self.config['review_kind'] == 'automated_test'
                             and review['status'] == 'automated_test_fixture')
            files = {key: {'url': '/api/files/'+key, 'sha256': selection['files'][key]['sha256'],
                              'byte_length': selection['files'][key]['byte_length']} for key in ('motion','repair')}
            files['audio'] = {key: value for key, value in self.config['audio'].items() if key != 'path'}
            files['audio']['url'] = '/api/files/audio'
            return {'format': WORKSPACE_FORMAT, 'schema_version': 1, 'revision': state['revision'],
                'scene_id': self.config['scene_id'], 'selection': selection, 'target': self.config['target'], 'files': files,
                'boundary_range_seconds': self.config['boundary_range_seconds'], 'review_kind': self.config['review_kind'],
                'alignment': {'report': report, 'report_sha256': report_sha, 'report_content_sha256': timing_hash(report)},
                'timing_revision': timing, 'timing_revision_content_sha256': timing_hash(timing) if timing else None,
                'review': review, 'draft': state['draft'], 'export_ready': ready}

    def finish(self, body):
        allowed = {'expected_revision','start_seconds','end_seconds','beats'}
        if set(body) != allowed:
            raise ScoreError('Finish needs explicit start, end and beat count')
        start, end, beats = body['start_seconds'], body['end_seconds'], body['beats']
        if (type(start) not in (int, float) or type(end) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(end)):
            raise ScoreError('Loop boundaries must be finite source seconds')
        a, b = self.config['boundary_range_seconds']
        if not a <= start < end <= b:
            raise ScoreError('Choose bounds inside this reviewed continuous source segment')
        with self._mutation(body['expected_revision']) as state:
            relative = 'selections/'+uuid.uuid4().hex
            finish_review_selection(self._path(self.config['inputs']['capture']['path']), self._path(relative),
                start_seconds=start, end_seconds=end, beats=beats,
                original_source_sha256=self.config['original_source_sha256'],
                repair_options=self.config['repair_options'], verify_native=True)
            state.update(selection_dir=relative, review=None, last_review=None, last_export=None)
            state['draft'].update(start_seconds=start, end_seconds=end, beats=beats,
                verdicts={'seam': 'unreviewed','feet': 'unreviewed','skin': 'unreviewed'})
        return self.session()

    def draft(self, body):
        if set(body) != {'expected_revision','draft'} or not isinstance(body['draft'], dict):
            raise ScoreError('Expected a draft object and its current revision')
        allowed = {'candidate_id','offset_seconds','manual_anchors','reviewer','beat_one_audio_seconds',
                   'meter','verdicts','notes','start_seconds','end_seconds','beats'}
        if set(body['draft'])-allowed or len(canonical_json(body['draft'])) > 200000:
            raise ScoreError('Invalid or oversized draft')
        with self._mutation(body['expected_revision']) as state:
            state.update(draft=body['draft'], review=None, last_export=None)
        return self.session()

    def review(self, body):
        from stemlab.analysis.motion_alignment import document_hash as timing_hash
        from stemlab.analysis.motion_alignment import (
            read_document,
            validate_alignment_revision,
        )

        required = {'expected_revision','timing_revision','reviewer','verdicts','review_kind','notes'}
        if (not required <= set(body) or set(body)-(required|{'draft'})
                or body['review_kind'] != self.config['review_kind']):
            raise ScoreError('Review fields or review kind differ from this workspace')
        if not isinstance(body['reviewer'], str):
            raise ScoreError('Reviewer must be a name')
        if 'draft' in body and (not isinstance(body['draft'], dict)
                               or len(canonical_json(body['draft'])) > 200000):
            raise ScoreError('Invalid review form state')
        with self._mutation(body['expected_revision']) as state:
            report_path = self._path(self.config['inputs']['alignment']['path'])
            report, report_sha = read_document(report_path)
            timing = body['timing_revision']
            validate_alignment_revision(report, timing, report_sha256=report_sha)
            previous_timing = read_review(self._path(state['timing_revision'])) if state['timing_revision'] else None
            if previous_timing:
                if (timing['previous_revision_sha256'] != timing_hash(previous_timing)
                        or timing['revision'] != previous_timing['revision']+1):
                    raise StaleRevisionError('Timing revision does not follow the last saved decision')
            elif timing['revision'] != 1 or timing['previous_revision_sha256'] is not None:
                raise ScoreError('The first timing decision must begin a new revision chain')
            if timing['reviewer'] != body['reviewer'].strip():
                raise ScoreError('Timing and visual decisions must identify the same reviewer')
            folder = self.root/'reviews'/uuid.uuid4().hex
            folder.mkdir()
            try:
                write_review(folder/'timing.json', timing)
                previous = read_review(self._path(state['last_review'])) if state['last_review'] else None
                record = create_loop_review(self._path(state['selection_dir']),
                    alignment_report_path=report_path, timing_revision_path=folder/'timing.json',
                    audio_source_path=self.config['audio']['path'], target=self.config['target'],
                    reviewer=body['reviewer'], verdicts=body['verdicts'],
                    review_kind=body['review_kind'], notes=body['notes'], previous_review=previous)
                write_review(folder/'review.json', record)
            except BaseException:
                shutil.rmtree(folder)
                raise
            relative = folder.relative_to(self.root).as_posix()
            state.update(timing_revision=relative+'/timing.json', review=relative+'/review.json',
                last_review=relative+'/review.json', draft=body.get('draft',{}), last_export=None)
        return self.session()

    def export(self, body):
        if set(body) != {'expected_revision','package_id','version','title'}:
            raise ScoreError('Export needs a package id, version and title')
        with self._mutation(body['expected_revision']) as state:
            if not state['review']:
                raise ScoreError('Save the timing and visual decisions before exporting')
            record = read_review(self._path(state['review']))
            relative = 'exports/'+uuid.uuid4().hex
            destination = self._path(relative)
            destination.mkdir()
            try:
                export_reviewed_loop(self._path(state['selection_dir']), record, destination/'package',
                    audio_source_path=self.config['audio']['path'], expected_target=self.config['target'],
                    package_id=body['package_id'], version=body['version'], title=body['title'],
                    license=self.config['license'], provenance={'authoring': 'local imported-Action review',
                        'original_source_sha256': self.config['original_source_sha256']},
                    allow_test_review=self.config['review_kind']=='automated_test')
                archive = destination/'reviewed-loop.zip'
                export_motion_package(destination/'package', archive)
                state['last_export'] = dict(path=relative+'/reviewed-loop.zip', **descriptor(archive))
            except BaseException:
                shutil.rmtree(destination)
                raise
        return dict(url='/api/files/package', filename='reviewed-loop.zip',
                    revision=self._state()['revision'], **descriptor(archive))

    def file(self, logical_id):
        with self.lock:
            self._verify_inputs(include_site=True)
            state = self._state()
            if logical_id == 'audio':
                return checked(Path(self.config['audio']['path']), self.config['audio']), self.config['audio']['mime_type']
            if logical_id == 'package':
                item = state['last_export']
                if not item:
                    raise FileNotFoundError('No current reviewed package')
                return checked(self._path(item['path']), item), 'application/zip'
            if logical_id in ('motion','repair'):
                selection = load_selection(self._path(state['selection_dir']))
                item = selection['files'][logical_id]
                return checked(self._path(state['selection_dir']+'/'+item['path']), item), 'application/json'
            raise FileNotFoundError('Unknown review asset')


def create_server(workspace, *, port=0, token=None):
    """Bind only loopback; each instance has an unguessable per-run capability."""
    workspace = workspace if isinstance(workspace, ReviewWorkspace) else ReviewWorkspace(workspace)
    token = token or secrets.token_urlsafe(32)
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token):
        raise ValueError('Review token must be a random URL-safe capability')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'DanceRudimentsReview/1'

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            pass  # No media paths, request contents or capabilities enter logs.

        def _headers(self, status, mime, length, **headers):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(length))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; "
                "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            for key, value in headers.items():
                self.send_header(key.replace('_','-'), str(value))
            self.end_headers()

        def _json(self, status, value, **headers):
            raw = (canonical_json(value)+'\n').encode('ascii')
            self._headers(status,'application/json',len(raw),**headers)
            if self.command != 'HEAD':
                self.wfile.write(raw)

        def _guard(self, *, authenticated=False, source_asset=False):
            expected_host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected_host:
                self._json(403,{'error': 'Unexpected local review host'})
                return False
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://'+expected_host:
                self._json(403,{'error': 'Cross-origin review requests are not accepted'})
                return False
            if authenticated and not secrets.compare_digest(self.headers.get('X-Loop-Review-Token',''), token):
                self._json(403,{'error': 'Open the review URL printed by this server'})
                return False
            if source_asset:
                from http.cookies import CookieError, SimpleCookie
                cookie = SimpleCookie()
                try:
                    cookie.load(self.headers.get('Cookie',''))
                    value = cookie.get(f'loop_review_{self.server.server_port}')
                    accepted = value is not None and secrets.compare_digest(value.value,token)
                except (CookieError, TypeError, ValueError):
                    accepted = False
                if not accepted:
                    self._json(403,{'error': 'Authenticate this workspace before loading its source assets'})
                    return False
            return True

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path.startswith('//'):
                return self._json(400,{'error': 'Invalid request path'})
            if not self._guard(authenticated=path.startswith('/api/'),
                               source_asset=path.startswith(('/motions/','/characters/'))):
                return
            try:
                if path == '/api/session':
                    return self._json(200,workspace.session(),
                        Set_Cookie=f'loop_review_{self.server.server_port}={token}; Path=/; HttpOnly; SameSite=Strict')
                if path.startswith('/api/files/'):
                    target, mime = workspace.file(path[len('/api/files/'):])
                else:
                    name = 'index.html' if path == '/' else path.lstrip('/')
                    item = workspace.config['site']['files'].get(name)
                    if not item:
                        raise FileNotFoundError('Unknown site asset')
                    target = checked(owned(workspace.root/'site',name),item)
                    mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
                    if name.endswith('.wasm'):
                        mime = 'application/wasm'
                    elif name.endswith('.json.gz'):
                        mime = 'application/gzip'
                size = target.stat().st_size
                start, stop, status = 0, size, 200
                range_header = self.headers.get('Range')
                if range_header:
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)',range_header)
                    if not match:
                        self._headers(416,mime,0,Content_Range=f'bytes */{size}')
                        return
                    start = int(match[1]); stop = int(match[2])+1 if match[2] else size
                    if not 0 <= start < stop <= size:
                        self._headers(416,mime,0,Content_Range=f'bytes */{size}')
                        return
                    status = 206
                headers = {'Accept_Ranges': 'bytes'}
                if status == 206:
                    headers['Content_Range'] = f'bytes {start}-{stop-1}/{size}'
                self._headers(status,mime,stop-start,**headers)
                if self.command != 'HEAD':
                    with target.open('rb') as stream:
                        stream.seek(start)
                        remaining = stop-start
                        while remaining:
                            block = stream.read(min(remaining,1024*1024))
                            if not block:
                                raise OSError('Asset changed while reading')
                            self.wfile.write(block)
                            remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                return
            except FileNotFoundError:
                self._json(404,{'error': 'Review asset is unavailable'})
            except (ScoreError, ValueError, KeyError, OSError) as exc:
                self._json(409,{'error': str(exc)})

        def do_POST(self):
            if not self._guard(authenticated=True):
                return
            try:
                if self.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
                    return self._json(415,{'error': 'Use application/json'})
                if self.headers.get('Transfer-Encoding'):
                    return self._json(400,{'error': 'Streaming requests are not accepted'})
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= MAX_REQUEST:
                    return self._json(413,{'error': 'Review request exceeds its size limit'})
                body = strict_json(self.rfile.read(length))
                action = {'/api/finish':workspace.finish, '/api/draft':workspace.draft,
                          '/api/review':workspace.review, '/api/export':workspace.export}.get(urlsplit(self.path).path)
                if not action:
                    return self._json(404,{'error': 'Unknown review operation'})
                return self._json(200,action(body))
            except StaleRevisionError as exc:
                self._json(409,{'error': str(exc)})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                return
            except (ScoreError, ValueError, TypeError, KeyError, OSError) as exc:
                self._json(400,{'error': str(exc)})

    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads = True
    server.review_token = token
    server.review_url = f'http://127.0.0.1:{server.server_port}/#review={token}'
    server.workspace = workspace
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    prepare = commands.add_parser('prepare',help='Prepare an explicitly selected local Action and audio master')
    for name in ('capture','audio','alignment-report','output','original-source-sha256','calibration-capture','license-json'):
        prepare.add_argument('--'+name,required=True)
    for name in ('start-seconds','end-seconds','calibration-seconds'):
        prepare.add_argument('--'+name,type=float,required=True)
    prepare.add_argument('--beats',type=int,required=True)
    prepare.add_argument('--repair-options')
    prepare.add_argument('--retarget-map')
    prepare.add_argument('--title',default='Imported Action loop review')
    prepare.add_argument('--automated-test',action='store_true',help='Label every review/export as an unapproved test fixture')
    serve = commands.add_parser('serve',help='Open a prepared workspace on loopback')
    serve.add_argument('workspace')
    serve.add_argument('--port',type=int,default=0)
    inspect = commands.add_parser('inspect',help='Validate a workspace and print its public session state')
    inspect.add_argument('workspace')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            values = vars(args).copy(); values.pop('command')
            values['license'] = strict_json(Path(values.pop('license_json')).read_bytes())
            for key in ('repair_options','retarget_map'):
                values[key] = strict_json(Path(values[key]).read_bytes()) if values[key] else None
            result = prepare_workspace(**values)
            print(json.dumps(result,indent=2,ensure_ascii=True))
        elif args.command == 'inspect':
            print(json.dumps(ReviewWorkspace(args.workspace).session(),indent=2,ensure_ascii=True))
        else:
            preflight(Path(args.workspace))
            server = create_server(args.workspace,port=args.port)
            print('Open this local review URL in your browser:\n'+server.review_url,flush=True)
            try:
                server.serve_forever(poll_interval=.25)
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        return 0
    except (ScoreError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print('loop-review: '+str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
