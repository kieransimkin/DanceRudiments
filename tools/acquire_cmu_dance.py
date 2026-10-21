#!/usr/bin/env python3
"""Rebuild the reviewed CMU dance source ZIP from pinned public mirror bytes.

Downloads require --download. No source code is executed and no I/O occurs on
module import. Original BVH headers and calibration frames stay unchanged;
evidenced timing corrections belong to the separate offline import plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'motion-packages/cmu-dance-sources.json'
LICENSE_PATH = ROOT / 'motion-packages/licenses/CMU-Mocap.txt'
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('ascii')


def _digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest key: ' + key)
        result[key] = value
    return result


def load_manifest(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Source manifest exceeds 2 MiB')
    document = json.loads(path.read_text('utf-8'), object_pairs_hook=_unique_object)
    if (not isinstance(document, dict) or document.get('schema_version') != 1 or
            document.get('format') != 'dancerudiments.cmu-dance-source-files' or
            document.get('source_id') != 'cmu_dance'):
        raise ValueError('Unsupported CMU source manifest')
    commit = document.get('mirror_commit', '')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Mirror commit must be immutable')
    prefix = 'https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/' + commit + '/'
    files, support = document.get('files'), document.get('support_files')
    if (not isinstance(files, list) or not 1 <= len(files) <= 128 or
            not isinstance(support, list) or len(support) > 3):
        raise ValueError('Invalid source file count')
    paths, members, total = set(), set(), 0
    for item in files + support:
        if not isinstance(item, dict):
            raise ValueError('Source entry must be an object')
        cache_path, member, url = item.get('cache_path'), item.get('member'), item.get('download_url')
        if (not isinstance(cache_path, str) or not isinstance(member, str) or
                not isinstance(url, str) or not url.startswith(prefix) or
                any(c in url for c in ('?', '#', '\\'))):
            raise ValueError('Expected a pinned public mirror URL and safe paths')
        for value in (cache_path, member):
            if (not re.fullmatch(r'[A-Za-z0-9_./-]+', value) or
                    PurePosixPath(value).is_absolute() or
                    any(p in ('', '.', '..') for p in value.split('/'))):
                raise ValueError('Source member/cache path must be safe and relative')
        if cache_path.lower() in paths or member.lower() in members or member in ('LICENSE.txt', 'source-record.json'):
            raise ValueError('Duplicate or reserved source member/cache path')
        paths.add(cache_path.lower()); members.add(member.lower())
        if item in files and (cache_path != 'raw/' + item['id'] + '.bvh' or member != 'bvh/' + item['id'] + '.bvh'):
            raise ValueError('BVH paths must match their original motion ID')
        size = item.get('byte_length')
        if type(size) is not int or not 1 <= size <= 8 * 1024 * 1024:
            raise ValueError('Invalid source byte length')
        total += size
        for key, length in (('sha256', 64), ('git_blob_sha1', 40)):
            if not isinstance(item.get(key), str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', item[key]):
                raise ValueError('Source SHA-256 and Git blob identity are required')
    if total > MAX_TOTAL_BYTES:
        raise ValueError('Source collection exceeds the explicit download budget')
    archive = document.get('archive', {})
    if (archive.get('name') != 'cmu-dance-original-bvh.zip' or
            not isinstance(archive.get('sha256'), str) or
            not re.fullmatch(r'[0-9a-f]{64}', archive['sha256'])):
        raise ValueError('Expected the pinned deterministic archive identity')
    if document.get('license', {}).get('id') != 'LicenseRef-CMU-Mocap':
        raise ValueError('The source retains its custom CMU terms')
    _json_bytes(document)
    return document


def _preflight(parent):
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cmu-probe-', dir=parent) as temporary:
        before = Path(temporary) / 'before'
        before.write_bytes(b'cmu-source-probe')
        if before.read_bytes() != b'cmu-source-probe':
            raise OSError('Temporary directory probe failed')
        after = before.with_name('after'); before.rename(after); after.unlink()


def _verify(path, item):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != item['byte_length']:
        raise ValueError(f'{path.name}: invalid cached source type/length')
    data = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
    if hashlib.sha256(data).hexdigest() != item['sha256'] or blob != item['git_blob_sha1']:
        raise ValueError(f'{path.name}: source hash differs from pinned commit')
    if path.suffix == '.bvh' and not data.lstrip().startswith(b'HIERARCHY'):
        raise ValueError(f'{path.name}: source is not BVH data')


def _ensure_file(root, item, *, download):
    path = root / item['cache_path']
    if path.exists() or path.is_symlink():
        _verify(path, item)
        return
    if not download:
        raise FileNotFoundError(f'{path}: use --download to fetch the reviewed public source')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cmu-download-', dir=path.parent) as temporary:
        partial = Path(temporary) / path.name
        request = urllib.request.Request(item['download_url'], headers={
            'User-Agent': 'DanceRudiments-CMU-source-acquisition/1.0'})
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 200:
                raise ValueError(f'{path.name}: HTTP {response.status}')
            data = response.read(item['byte_length'] + 1)
        partial.write_bytes(data)
        _verify(partial, item)
        os.link(partial, path)


def _write_archive(document, root, output):
    licence = LICENSE_PATH.read_bytes()
    if hashlib.sha256(licence).hexdigest() != document['license']['local_text_sha256']:
        raise ValueError('Local source terms changed from the reviewed manifest')
    record = {key: value for key, value in document.items() if key != 'archive'}
    record['format'] = 'dancerudiments.motion-source-record'
    payloads = {'LICENSE.txt': licence, 'source-record.json': _json_bytes(record)}
    files = {item['member']: item for item in document['files'] + document['support_files']}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for member in sorted(set(files) | set(payloads)):
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = 0o100644 << 16
            if member in payloads:
                data = payloads[member]
            else:
                path = root / files[member]['cache_path']
                _verify(path, files[member]); data = path.read_bytes()
            archive.writestr(info, data)


def acquire(document, cache_root, *, download=False):
    root = Path(cache_root); _preflight(root)
    for item in document['files'] + document['support_files']:
        _ensure_file(root, item, download=download)
    output = root / document['archive']['name']
    expected = document['archive']['sha256']
    if output.exists() or output.is_symlink():
        if output.is_symlink() or _digest(output) != expected:
            raise ValueError('Existing source archive differs and was not overwritten')
    else:
        with tempfile.TemporaryDirectory(prefix='.cmu-archive-', dir=root) as temporary:
            partial = Path(temporary) / output.name
            _write_archive(document, root, partial)
            if _digest(partial) != expected:
                raise ValueError('Deterministic source archive differs from its reviewed hash')
            os.link(partial, output)
    return {'source_id': document['source_id'], 'path': str(output), 'sha256': expected,
            'byte_length': output.stat().st_size, 'source_files': len(document['files']),
            'unique_byte_sequences': len({x['sha256'] for x in document['files']})}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--cache-root', type=Path, default=ROOT / '.cache/motion-sources/cmu-dance')
    parser.add_argument('--download', action='store_true', help='Explicitly fetch missing pinned public source bytes')
    args = parser.parse_args(argv)
    print(json.dumps(acquire(load_manifest(args.manifest), args.cache_root, download=args.download), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
