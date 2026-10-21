"""Optional, rig-specific motion packages with lazy, bounded local loading.

Importing this module reads no catalogues, motion data or remote resources.
Packages contain one exact profile and individually addressed standard Recording
documents. Playback remains the existing native SampledRecording implementation.
"""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

from ._validation import ScoreError, canonical_json, fields, integer, name, text
from .io import _pairs
from .motion import RigMotion
from .recording import Recording, MAX_JSON_BYTES, MAX_RECORDING_VALUES, _write_bytes_document
from .rigs import RigProfile, canonical_type_uri

FORMAT = 'dancerudiments.motion-package'
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_CLIPS = 10_000
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024 * 1024
_HASH = re.compile(r'[0-9a-f]{64}')
_SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)?(?:\+[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)?')
_PATH = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*')
_NOTICES = {'README.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'SOURCES.json'}
_BUILD_CHECKPOINT = '.motion-package-build.json'


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash(value, label):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ScoreError(f'{label}: expected lowercase SHA-256')
    return value


def _path(value):
    if (not isinstance(value, str) or len(value) > 512 or not _PATH.fullmatch(value)
            or any(p in ('.', '..') for p in value.split('/'))):
        raise ScoreError('Package paths must be plain relative asset paths without traversal or URLs')
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ScoreError(f'{label}: expected a finite JSON object')
    canonical_json(value)
    return value


def _json(data, label):
    try:
        return json.loads(data, object_pairs_hook=_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ScoreError(f'Non-finite JSON: {x}')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ScoreError(f'{label}: invalid JSON: {exc}') from exc


def _read(path, limit):
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ScoreError(f'{path}: exceeds the bounded document size')
    return data


def validate_manifest(document):
    """Validate and return an independent metadata-only manifest copy."""
    required = {'format', 'schema_version', 'id', 'version', 'title', 'type_uri',
                'profile_sha256', 'dimensions', 'profile', 'clips', 'license', 'provenance'}
    fields(document, required, required, 'motion package')
    if document['format'] != FORMAT:
        raise ScoreError(f'Expected {FORMAT}')
    integer(document['schema_version'], 1, 1, 'schema_version')
    name(document['id'], 'package.id')
    if not isinstance(document['version'], str) or not _SEMVER.fullmatch(document['version']):
        raise ScoreError('package.version must be a semantic version string')
    pre = document['version'].split('+', 1)[0].partition('-')[2]
    if any(part.isdigit() and len(part) > 1 and part.startswith('0') for part in pre.split('.')):
        raise ScoreError('Semantic version numeric prerelease identifiers cannot have leading zeros')
    if not text(document['title'], 'title').strip() or len(document['title']) > 1024:
        raise ScoreError('package.title must be nonempty and at most 1024 characters')
    if canonical_type_uri(document['type_uri']) != document['type_uri']:
        raise ScoreError('Package type_uri must use canonical syn:// identity')
    _hash(document['profile_sha256'], 'profile_sha256')
    dims = document['dimensions']
    if not isinstance(dims, list) or not 1 <= len(dims) <= 1_000_000:
        raise ScoreError('Package dimensions must be a nonempty bounded array')
    for dim in dims:
        name(dim, 'dimension')
    if len(set(dims)) != len(dims):
        raise ScoreError('Package dimensions must be unique and ordered')
    p = document['profile']
    fields(p, {'path', 'sha256', 'byte_length'}, {'path', 'sha256', 'byte_length'}, 'profile asset')
    _path(p['path']); _hash(p['sha256'], 'profile.sha256')
    if p['path'].lower() in {s.lower() for s in _NOTICES | {'manifest.json'}}:
        raise ScoreError('Profile asset cannot replace the manifest or package notices')
    integer(p['byte_length'], 1, MAX_JSON_BYTES, 'profile.byte_length')
    if p['sha256'] != document['profile_sha256']:
        raise ScoreError('Profile bytes must have the canonical profile fingerprint')
    clips = document['clips']
    if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS:
        raise ScoreError(f'Package must contain 1..{MAX_CLIPS} clip descriptors')
    ids, paths = set(), {s.lower() for s in {p['path'], 'manifest.json'} | _NOTICES}
    keys = {'id', 'path', 'sha256', 'byte_length', 'decoded_byte_length', 'encoding', 'start_pip', 'sample_count'}
    for c in clips:
        fields(c, keys | {'metadata'}, keys, 'clip descriptor')
        name(c['id'], 'clip.id'); _path(c['path']); _hash(c['sha256'], 'clip.sha256')
        if c['id'] in ids or c['path'].lower() in paths:
            raise ScoreError('Clip IDs and package asset paths must be unique')
        ids.add(c['id']); paths.add(c['path'].lower())
        integer(c['byte_length'], 1, MAX_JSON_BYTES, 'clip.byte_length')
        integer(c['decoded_byte_length'], 1, MAX_JSON_BYTES, 'clip.decoded_byte_length')
        integer(c['start_pip'], -2147483648, 2147483647, 'clip.start_pip')
        integer(c['sample_count'], 1, MAX_RECORDING_VALUES // len(dims), 'clip.sample_count')
        if c['start_pip'] + c['sample_count'] > 2147483647:
            raise ScoreError('Clip exceeds the native signed int32 pip range')
        if c['encoding'] not in ('json', 'gzip'):
            raise ScoreError('Clip encoding must be json or gzip')
        if c['encoding'] == 'json' and c['decoded_byte_length'] != c['byte_length']:
            raise ScoreError('JSON stored and decoded byte lengths must match')
        metadata = _object(c.get('metadata', {}), 'clip.metadata')
        if 'timing_kind' in metadata and metadata['timing_kind'] not in ('music', 'time-only'):
            raise ScoreError('timing_kind must distinguish music from time-only motion')
    _object(document['license'], 'license'); _object(document['provenance'], 'provenance')
    encoded = canonical_json(document).encode('ascii')
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ScoreError('Package manifest exceeds 8 MiB')
    return json.loads(encoded)


class MotionPackage:
    """One explicit local package; only requested profiles/clips enter memory.

    At most one clip is cached by default. Caller-owned RigMotion objects remain
    usable after eviction. No global registration, filesystem search, native
    initialization, download or optional-data import occurs automatically.
    """

    def __init__(self, path, *, expected_profile=None, manifest_sha256=None, cache_size=1):
        path = Path(path)
        self._manifest_path = path / 'manifest.json' if path.is_dir() else path
        self._root = self._manifest_path.parent.resolve()
        payload = _read(self._manifest_path, MAX_MANIFEST_BYTES)
        if manifest_sha256 is not None and _digest(payload) != _hash(manifest_sha256, 'manifest_sha256'):
            raise ScoreError('Package manifest SHA-256 mismatch')
        self._manifest = validate_manifest(_json(payload, 'manifest'))
        integer(cache_size, 0, MAX_CLIPS, 'cache_size')
        if expected_profile is not None:
            if not isinstance(expected_profile, RigProfile):
                raise ScoreError('expected_profile must be an exact RigProfile')
            if (expected_profile.fingerprint != self._manifest['profile_sha256']
                    or expected_profile.type_uri != self._manifest['type_uri']
                    or list(expected_profile.dimensions) != self._manifest['dimensions']):
                raise ScoreError('Package does not match the scene rig profile; explicit retargeting is required')
        self._cache_size = cache_size
        self._cache = OrderedDict()
        self._profile = None
        self._closed = False
        self._clips = {c['id']: c for c in self._manifest['clips']}

    def _check_open(self):
        if self._closed:
            raise RuntimeError('MotionPackage is closed')

    @property
    def manifest(self):
        self._check_open()
        return json.loads(canonical_json(self._manifest))

    @property
    def cached_clip_ids(self):
        return tuple(self._cache)

    def catalogue(self):
        """Metadata only: does not read the profile or any clip payload."""
        return self.manifest['clips']

    def _asset(self, descriptor):
        target = (self._root / _path(descriptor['path'])).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise ScoreError('Package asset resolves outside its directory') from exc
        if not target.is_file():
            raise ScoreError(f'Missing package asset: {descriptor["path"]}')
        data = _read(target, descriptor['byte_length'])
        if len(data) != descriptor['byte_length'] or _digest(data) != descriptor['sha256']:
            raise ScoreError(f'Package asset integrity mismatch: {descriptor["path"]}')
        return data

    @property
    def profile(self):
        self._check_open()
        if self._profile is None:
            self._profile = RigProfile.from_dict(_json(self._asset(self._manifest['profile']), 'profile'))
            if (self._profile.fingerprint != self._manifest['profile_sha256']
                    or self._profile.type_uri != self._manifest['type_uri']
                    or list(self._profile.dimensions) != self._manifest['dimensions']):
                self._profile = None
                raise ScoreError('Profile identity or channel order differs from the package manifest')
        return self._profile

    def load(self, clip_id):
        self._check_open()
        if clip_id not in self._clips:
            raise KeyError(f'Unknown package clip: {clip_id}')
        if clip_id in self._cache:
            self._cache.move_to_end(clip_id)
            return self._cache[clip_id]
        profile = self.profile
        desc = self._clips[clip_id]
        payload = self._asset(desc)
        if desc['encoding'] == 'gzip':
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                    payload = stream.read(desc['decoded_byte_length'] + 1)
            except (OSError, EOFError) as exc:
                raise ScoreError('Invalid compressed clip') from exc
        if len(payload) != desc['decoded_byte_length']:
            raise ScoreError('Decoded clip size differs from manifest or exceeds its limit')
        recording = Recording.from_dict(_json(payload, 'recording'))
        if (recording.name != clip_id or recording.clock.start_pip != desc['start_pip']
                or len(recording.samples) != desc['sample_count']):
            raise ScoreError('Clip identity or pip bounds differ from its manifest')
        motion = RigMotion(recording, profile)
        if self._cache_size:
            self._cache[clip_id] = motion
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return motion

    def unload(self, clip_id):
        self._cache.pop(clip_id, None)

    def close(self):
        self._cache.clear()
        self._profile = None
        self._closed = True

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *args):
        self.close()


class MotionPackageBuilder:
    """Write an optional directory with one profile and compressed per-clip data."""

    def __init__(self, output, *, package_id, version, title, profile, license, provenance, resume=False):
        self.output = Path(output)
        if not isinstance(profile, RigProfile):
            raise ScoreError('Package builder requires a validated exact rig profile')
        self.profile = profile
        payload = canonical_json(profile.to_dict()).encode('ascii')
        self._manifest = dict(format=FORMAT, schema_version=1, id=package_id, version=version,
                              title=title, type_uri=profile.type_uri, profile_sha256=profile.fingerprint,
                              dimensions=list(profile.dimensions),
                              profile=dict(path='profile.json', sha256=_digest(payload), byte_length=len(payload)),
                              clips=[], license=license, provenance=provenance)
        self._ids = set()
        self._resume = resume
        self._batch_active = False
        self._written_assets = set()
        # Validate identity/metadata before creating anything, using one temporary descriptor.
        probe = dict(self._manifest, clips=[dict(id='validation_probe', path='clips/probe.json',
                     sha256='0'*64, byte_length=1, decoded_byte_length=1, encoding='json', start_pip=0, sample_count=1)])
        validate_manifest(probe)
        if self.output.exists() and any(self.output.iterdir()):
            if not resume:
                raise ScoreError('Package output must be empty unless resume=True')
            if (self.output / 'manifest.json').exists():
                with MotionPackage(self.output, expected_profile=profile, cache_size=0) as previous:
                    old = previous.manifest
                    for k in set(old) - {'clips'}:
                        if old[k] != self._manifest[k]:
                            raise ScoreError(f'Cannot resume a package with changed {k}')
                    previous.profile  # checks bytes and identity
                    self._manifest['clips'] = old['clips']
                    self._ids = {c['id'] for c in old['clips']}
            else:
                checkpoint = self.output / _BUILD_CHECKPOINT
                if not checkpoint.is_file() or _json(_read(checkpoint, MAX_MANIFEST_BYTES), 'build checkpoint') != self._manifest:
                    raise ScoreError('Cannot resume an unpublished package without its exact build identity')
                profile_path = self.output / 'profile.json'
                if profile_path.exists():
                    if _read(profile_path, len(payload)) != payload:
                        raise ScoreError('Interrupted package profile differs from the requested identity')
                else:
                    _write_bytes_document(profile_path, payload)
        else:
            self.output.mkdir(parents=True, exist_ok=True)
            # Record identity before the first asset, so interruption at any
            # later write can be resumed without claiming unrelated files.
            _write_bytes_document(self.output / _BUILD_CHECKPOINT,
                                  canonical_json(self._manifest).encode('ascii'))
            _write_bytes_document(self.output / 'profile.json', payload)

    @contextmanager
    def atomic_batch(self):
        """Publish a complete action's clips together, or keep the old manifest.

        Failed writes can leave unadvertised immutable assets. A retry adopts
        them only when their bytes are identical; no partial action becomes
        visible through the package catalogue.
        """
        if self._batch_active:
            raise ScoreError('Package batches cannot be nested')
        previous_clips, previous_ids = list(self._manifest['clips']), set(self._ids)
        self._batch_active = True
        try:
            yield self
            self._batch_active = False
            self.finalize()
        except BaseException:
            self._manifest['clips'] = previous_clips
            self._ids = previous_ids
            raise
        finally:
            self._batch_active = False

    def add(self, motion, *, metadata=None, encoding='gzip'):
        if not isinstance(motion, RigMotion):
            raise ScoreError('add requires a validated RigMotion')
        motion.require_profile(self.profile)
        return self._add_document(motion.recording.to_dict(), metadata=metadata, encoding=encoding)

    def add_bvh_chunk(self, chunk, *, metadata=None, encoding='gzip'):
        """Add an explicitly validated vectorized offline BVH import chunk.

        NumPy is imported only by this optional authoring path. The result is
        the same standard Recording JSON used by native playback, without an
        additional Python sampler or a second format for large recordings.
        """
        from .bvh_import import BVHMotionChunk
        if not isinstance(chunk, BVHMotionChunk):
            raise ScoreError('add_bvh_chunk requires a BVHMotionChunk')
        chunk.validate()
        if (chunk.profile.fingerprint != self.profile.fingerprint or
                chunk.profile.dimensions != self.profile.dimensions):
            raise ScoreError('BVH chunk must match the package profile exactly')
        combined = chunk.metadata
        combined.update(_object(metadata or {}, 'metadata'))
        return self._add_document(chunk.to_recording_dict(), metadata=combined, encoding=encoding)

    def _add_document(self, document, *, metadata=None, encoding='gzip'):
        clip_id = document['name']
        if clip_id in self._ids:
            raise ScoreError(f'Duplicate clip: {clip_id}')
        metadata = _object(metadata or {}, 'metadata')
        if encoding not in ('json', 'gzip'):
            raise ScoreError('encoding must be json or gzip')
        payload = canonical_json(document).encode('ascii')
        if len(payload) > MAX_JSON_BYTES:
            raise ScoreError('Clip exceeds 64 MiB JSON; split at explicit pip boundaries')
        data = payload
        if encoding == 'gzip':
            data = bytearray(gzip.compress(payload, compresslevel=6, mtime=0))
            data[9] = 255  # portable gzip OS marker, independent of the authoring platform
            data = bytes(data)
        relative = f'clips/{clip_id}.json' + ('.gz' if encoding == 'gzip' else '')
        desc = dict(id=clip_id, path=relative, sha256=_digest(data), byte_length=len(data),
                    decoded_byte_length=len(payload), encoding=encoding,
                    start_pip=document['clock']['start_pip'], sample_count=len(document['samples']), metadata=metadata)
        candidate = dict(self._manifest, clips=self._manifest['clips'] + [desc])
        validate_manifest(candidate)
        target = self.output / relative
        if target.exists():
            if not (self._resume or relative in self._written_assets):
                raise FileExistsError(target)
            if _read(target, len(data)) != data:
                raise ScoreError(f'Cannot adopt changed interrupted clip: {relative}')
        else:
            # The atomic writer may publish successfully and then fail during
            # temporary-file cleanup. Remember ownership before that call so
            # the same builder can recover the identical published bytes.
            self._written_assets.add(relative)
            _write_bytes_document(target, data)
        self._written_assets.add(relative)
        self._manifest['clips'].append(desc)
        self._ids.add(clip_id)
        return dict(desc)

    def finalize(self):
        if self._batch_active:
            raise ScoreError('Cannot publish a manifest before its atomic batch completes')
        document = validate_manifest(self._manifest)
        _write_bytes_document(self.output / 'manifest.json', canonical_json(document).encode('ascii'), overwrite=True)
        return document


def export_motion_package(directory, archive):
    """Create an independent ZIP; it is never added to a base package dependency."""
    package = MotionPackage(directory, cache_size=0)
    manifest = package.manifest
    package.profile
    root = Path(directory)
    if root.is_file(): root = root.parent
    files = ['manifest.json', manifest['profile']['path']] + [c['path'] for c in manifest['clips']]
    for desc in manifest['clips']:
        package._asset(desc)
    for filename in ('README.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'SOURCES.json'):
        if (root / filename).is_file(): files.append(filename)
    archive = Path(archive)
    if archive.exists():
        raise FileExistsError(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpname = tempfile.mkstemp(prefix='.motion-package-', suffix='.zip', dir=archive.parent)
    import os
    os.close(fd)
    try:
        with zipfile.ZipFile(tmpname, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for relative in sorted(files):
                source = (root / relative).resolve()
                source.relative_to(root.resolve())
                info = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                z.writestr(info, source.read_bytes())
        os.link(tmpname, archive)
    finally:
        Path(tmpname).unlink(missing_ok=True)
    package.close()
    return archive


def install_motion_package(archive, root, *, expected_sha256=None, max_total_bytes=MAX_ARCHIVE_BYTES):
    """Explicit local ZIP installation, validated and atomic; no code execution.

    The destination is <root>/<id>/<version>. Existing packages are preserved.
    Archives may contain only their declared profile/clips and standard notices.
    """
    archive, root = Path(archive), Path(root)
    integer(max_total_bytes, 1, MAX_ARCHIVE_BYTES, 'max_total_bytes')
    if expected_sha256 is not None:
        expected_sha256 = _hash(expected_sha256, 'expected_sha256')
        h = hashlib.sha256()
        with archive.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
        if h.hexdigest() != expected_sha256:
            raise ScoreError('Package archive SHA-256 mismatch')
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > MAX_CLIPS + 6:
            raise ScoreError('Archive has too many entries')
        names, folded_names = set(), set()
        total = 0
        for info in infos:
            _path(info.filename)
            file_type = stat.S_IFMT(info.external_attr >> 16)
            if info.filename.lower() in folded_names or info.is_dir() or file_type not in (0, stat.S_IFREG):
                raise ScoreError('Archive contains duplicate or non-regular file entries')
            names.add(info.filename)
            folded_names.add(info.filename.lower())
            if info.file_size > MAX_JSON_BYTES:
                raise ScoreError('Archive entry exceeds 64 MiB')
            total += info.file_size
        if total > max_total_bytes:
            raise ScoreError('Archive exceeds the configured total byte limit')
        if 'manifest.json' not in names or z.getinfo('manifest.json').file_size > MAX_MANIFEST_BYTES:
            raise ScoreError('Archive requires a bounded root manifest.json')
        document = validate_manifest(_json(z.read('manifest.json'), 'manifest'))
        allowed = {'manifest.json', document['profile']['path'], 'README.md', 'LICENSE.txt',
                   'THIRD_PARTY_NOTICES.md', 'SOURCES.json'} | {c['path'] for c in document['clips']}
        required = {'manifest.json', document['profile']['path']} | {c['path'] for c in document['clips']}
        if not required <= names or not names <= allowed:
            raise ScoreError('Archive entries differ from its declared assets and notices')
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve()
        parent = root / document['id']
        if parent.is_symlink():
            raise ScoreError('Package installation parent cannot be a symlink')
        try:
            parent.resolve().relative_to(root)
        except ValueError as exc:
            raise ScoreError('Package destination resolves outside the selected install root') from exc
        destination = parent / document['version']
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f'Package already installed: {destination}')
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.install-', dir=destination.parent) as temporary:
            staged = Path(temporary) / 'package'; staged.mkdir()
            for info in infos:
                path = staged / info.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, path.open('xb') as out:
                    shutil.copyfileobj(source, out, length=1024*1024)
            package = MotionPackage(staged, cache_size=0)
            package.profile
            for desc in document['clips']: package._asset(desc)
            package.close()
            # rename refuses replacement of a nonempty existing package.
            if parent.is_symlink() or parent.resolve().parent != root:
                raise ScoreError('Package installation parent changed during installation')
            if destination.exists() or destination.is_symlink(): raise FileExistsError(destination)
            staged.rename(destination)
    return destination


def discover_motion_packages(root):
    """Explicit metadata-only scan of one caller-selected install directory."""
    result = []
    for path in sorted(Path(root).glob('*/*/manifest.json')):
        package = MotionPackage(path, cache_size=0)
        m = package.manifest
        result.append(dict(id=m['id'], version=m['version'], title=m['title'], type_uri=m['type_uri'],
                           profile_sha256=m['profile_sha256'], clip_count=len(m['clips']), path=str(path)))
        package.close()
    return result
