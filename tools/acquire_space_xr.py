#!/usr/bin/env python3
"""Explicit, hash-pinned acquisition of the public Space-XR BVH recordings.

Importing this module performs no I/O. Running it without --download only uses
already cached source files. Each output is a deterministic, uncompressed ZIP
of unchanged BVHs plus their public attribution and per-file provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'motion-packages' / 'space-xr-sources.json'
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024


def _digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('ascii')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_manifest(path):
    """Validate the reviewed, small public file list before any output/network I/O."""
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Source manifest exceeds 2 MiB')
    document = json.loads(path.read_text('utf-8'), object_pairs_hook=_unique_object)
    if (not isinstance(document, dict) or
            document.get('format') != 'dancerudiments.space-xr-source-files' or
            document.get('schema_version') != 1):
        raise ValueError('Unsupported Space-XR source manifest')
    if (document.get('source_url') != 'https://visgraflab.impa.br/dance/?p=1' or
            document.get('license', {}).get('spdx') != 'CC-BY-SA-4.0'):
        raise ValueError('Expected the reviewed Space-XR source and CC-BY-SA-4.0 licence')
    archives = document.get('archives')
    if not isinstance(archives, list) or not 1 <= len(archives) <= 2:
        raise ValueError('Expected one or two separate source convention archives')
    ids, names, file_names, urls = set(), set(), set(), set()
    total = 0
    for archive in archives:
        if not isinstance(archive, dict):
            raise ValueError('Source archive must be an object')
        source_id, archive_name = archive.get('id'), archive.get('archive_name')
        if source_id not in ('space_xr_yup', 'space_xr_zup') or source_id in ids:
            raise ValueError('Source archive ID must be unique and identify its convention')
        if (not isinstance(archive_name, str) or
                not re.fullmatch(r'[a-z0-9][a-z0-9_-]*\.zip', archive_name) or
                archive_name in names):
            raise ValueError('Archive filename must be a unique plain ZIP filename')
        ids.add(source_id)
        names.add(archive_name)
        if not re.fullmatch(r'[0-9a-f]{64}', archive.get('sha256', '')):
            raise ValueError('Each deterministic source archive needs its expected SHA-256')
        files = archive.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= 32:
            raise ValueError('Source archive file list is invalid')
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('Source file must be an object')
            name = item.get('name')
            if (not isinstance(name, str) or
                    not re.fullmatch(r'[a-z0-9][a-z0-9_-]*\.bvh', name) or
                    name in file_names or item.get('member') != 'bvh/' + name):
                raise ValueError('BVH files need unique plain names and safe bvh/ members')
            file_names.add(name)
            url = item.get('download_url')
            if not isinstance(url, str):
                raise ValueError('Source file URL is missing')
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'visgraflab.impa.br' or
                    parsed.username or parsed.password or parsed.port or parsed.query or
                    parsed.fragment or not parsed.path.startswith('/dance/wp-content/uploads/') or
                    Path(parsed.path).name != name or url in urls):
                raise ValueError('Downloads must use the reviewed unique public HTTPS BVH URLs')
            urls.add(url)
            size = item.get('byte_length')
            if type(size) is not int or not 1 <= size <= MAX_FILE_BYTES:
                raise ValueError('Source file has an invalid byte bound')
            total += size
            if total > MAX_SOURCE_BYTES:
                raise ValueError('Source manifest exceeds the total download budget')
            if not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', '')):
                raise ValueError('Source file SHA-256 is missing')
    _json_bytes(document)  # Also rejects non-finite JSON values.
    return document


def _preflight(parent):
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.space-xr-probe-', dir=parent) as directory:
        before = Path(directory) / 'before'
        before.write_bytes(b'space-xr-probe')
        if before.read_bytes() != b'space-xr-probe':
            raise OSError('Temporary directory read/write probe failed')
        after = before.with_name('after')
        before.rename(after)
        after.unlink()


def _verify_file(path, item):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'{path.name}: expected a regular cached file')
    if path.stat().st_size != item['byte_length'] or _digest(path) != item['sha256']:
        raise ValueError(f'{path.name}: cached bytes differ from the reviewed source hash/size')
    with path.open('rb') as stream:
        if not stream.read(256).lstrip().startswith(b'HIERARCHY'):
            raise ValueError(f'{path.name}: response is not BVH data')


def _ensure_source(item, cache_root, *, download):
    path = cache_root / item['name']
    if path.exists() or path.is_symlink():
        _verify_file(path, item)
        return path
    if not download:
        raise FileNotFoundError(f'{path}: source is missing; use --download to fetch reviewed public files')
    request = urllib.request.Request(item['download_url'], headers={
        'User-Agent': 'DanceRudiments-Space-XR-acquisition/1.0'})
    with tempfile.TemporaryDirectory(prefix='.space-xr-download-', dir=cache_root) as temporary:
        partial = Path(temporary) / item['name']
        with urllib.request.urlopen(request, timeout=45) as response, partial.open('xb') as output:
            if response.status != 200:
                raise ValueError(f'{path.name}: HTTP {response.status}')
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != item['byte_length']:
                raise ValueError(f'{path.name}: remote Content-Length differs from the reviewed source')
            count = 0
            while block := response.read(256 * 1024):
                count += len(block)
                if count > item['byte_length']:
                    raise ValueError(f'{path.name}: download exceeded its reviewed byte length')
                output.write(block)
        _verify_file(partial, item)
        os.link(partial, path)  # Atomic creation; never overwrite an existing source.
    return path


def _source_record(document, archive):
    return {
        'format': 'dancerudiments.motion-source-record', 'schema_version': 1,
        'source_id': archive['id'], 'title': document['title'],
        'source_url': document['source_url'], 'creator': document['creator'],
        'license': document['license'], 'timing_kind': 'time-only',
        'music_beat_metadata': None, 'physical_unit': document['physical_unit'],
        'source_page_sha256': document['source_page_sha256'],
        'conversion': archive['conversion'], 'files': sorted(archive['files'], key=lambda x: x['member']),
        'changes': 'Original BVH bytes retained. Packaging and provenance records added; no retargeting or beat annotation.',
        'notes': document['notes'],
    }


def _license_bytes(document):
    return (
        f"{document['title']}\n\nSource: {document['source_url']}\n"
        f"Creator: {document['creator']}\n"
        'Performers: Thaisa Martins, Helena Bevilaqua, Fabiano Nunes; see source-record.json.\n\n'
        'The creator licenses these BVH downloads under Creative Commons\n'
        'Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).\n'
        'Licence: https://creativecommons.org/licenses/by-sa/4.0/\n'
        'Legal code: https://creativecommons.org/licenses/by-sa/4.0/legalcode.en\n\n'
        'Retain attribution and source links, indicate changes, and license adapted\n'
        'data under the same terms or a compatible licence as the legal code specifies.\n'
        'This archive preserves original source BVH bytes and adds packaging/provenance.\n'
        'The data licence is independent of the DanceRudiments software licence.\n'
        'The source provides no warranties. Do not imply creator endorsement.\n'
    ).encode('utf-8')


def _write_archive(document, archive, cache_root, output):
    """Write fixed ZIP_STORED bytes, independent of zlib versions and wall clocks."""
    payloads = {'source-record.json': _json_bytes(_source_record(document, archive)),
                'LICENSE.txt': _license_bytes(document)}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as result:
        entries = {item['member']: item for item in archive['files']}
        for name in sorted(set(entries) | set(payloads)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            if name in payloads:
                result.writestr(info, payloads[name])
            else:
                path = cache_root / entries[name]['name']
                _verify_file(path, entries[name])
                # Each file is already bounded to 50 MiB by the reviewed manifest.
                result.writestr(info, path.read_bytes())


def acquire(document, cache_root, *, source_ids=None, download=False):
    """Build selected archives from verified original files; no code is executed."""
    cache_root = Path(cache_root)
    selected = set(source_ids or [a['id'] for a in document['archives']])
    known = {a['id'] for a in document['archives']}
    if not selected <= known:
        raise ValueError('Unknown Space-XR source ID')
    _preflight(cache_root)
    reports = []
    for archive in document['archives']:
        if archive['id'] not in selected:
            continue
        for item in archive['files']:
            _ensure_source(item, cache_root, download=download)
        output = cache_root / archive['archive_name']
        if output.exists() or output.is_symlink():
            if output.is_symlink() or _digest(output) != archive['sha256']:
                raise ValueError(f'{output.name}: existing archive differs; it was not overwritten')
        else:
            with tempfile.TemporaryDirectory(prefix='.space-xr-archive-', dir=cache_root) as temporary:
                partial = Path(temporary) / archive['archive_name']
                _write_archive(document, archive, cache_root, partial)
                if _digest(partial) != archive['sha256']:
                    raise ValueError(f'{output.name}: deterministic archive hash does not match the reviewed manifest')
                os.link(partial, output)
        reports.append({'source_id': archive['id'], 'path': str(output),
                        'sha256': archive['sha256'], 'byte_length': output.stat().st_size,
                        'source_files': len(archive['files'])})
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--cache-root', type=Path, default=ROOT / '.cache/motion-sources/space-xr')
    parser.add_argument('--sources', nargs='+', choices=('space_xr_yup', 'space_xr_zup'))
    parser.add_argument('--download', action='store_true',
                        help='Explicitly fetch missing public source files; otherwise require the local cache')
    args = parser.parse_args(argv)
    document = load_manifest(args.manifest)
    reports = acquire(document, args.cache_root, source_ids=args.sources, download=args.download)
    print(json.dumps(reports, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
