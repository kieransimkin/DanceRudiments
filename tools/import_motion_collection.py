#!/usr/bin/env python3
"""Acquire explicitly selected public archives and build independent BVH packs.

The source plan is local, reviewed metadata. Nothing runs at package import or
installation. BVH conversion preserves source skeletons; it does not claim a
Rigify retarget or infer musical beats from filenames.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
from itertools import chain
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from dancerudiments_authoring._validation import ScoreError, canonical_json
from dancerudiments_authoring.motion_packages import MotionPackage, MotionPackageBuilder
from dancerudiments_authoring.recording import _write_bytes_document


def file_hash(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): result.update(block)
    return result.hexdigest()


def preflight(parent):
    parent = Path(parent); parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.probe-', dir=parent) as directory:
        path = Path(directory) / 'before'
        path.write_bytes(b'motion-package-preflight')
        assert path.read_bytes() == b'motion-package-preflight'
        renamed = path.with_name('after'); path.rename(renamed)
        assert renamed.read_bytes() == b'motion-package-preflight'
        renamed.unlink()


def asset_path(asset, cache_root):
    path = PurePosixPath(asset['cache_path'])
    if path.is_absolute() or '..' in path.parts or '\\' in str(path):
        raise ScoreError('Source cache_path must be a safe relative path')
    return cache_root / Path(*path.parts)


def verify_archive(path, asset):
    if asset.get('size_bytes') is not None and path.stat().st_size != asset['size_bytes']:
        raise ScoreError(f'{path.name}: size differs from source metadata')
    for algorithm in ('sha256', 'md5'):
        if asset.get(algorithm) and file_hash(path, algorithm) != asset[algorithm]:
            raise ScoreError(f'{path.name}: published {algorithm} differs')
    with path.open('rb') as stream:
        if stream.read(4) != b'PK\x03\x04': raise ScoreError(f'{path.name}: response is not a ZIP archive')
    with zipfile.ZipFile(path) as archive:
        if not archive.infolist(): raise ScoreError('Source archive is empty')
    return file_hash(path)


def download(asset, cache_root):
    path = asset_path(asset, cache_root)
    preflight(path.parent)
    if path.exists():
        digest = verify_archive(path, asset)
        return dict(path=str(path), sha256=digest, cached=True, byte_length=path.stat().st_size)
    if asset.get('local_archive'):
        raise ScoreError(f'Assemble this local source archive with its acquisition recipe first: {path}')
    url = asset['download_url']
    if not isinstance(url, str) or not url.startswith('https://'):
        raise ScoreError('Public source downloads must use explicit HTTPS URLs')
    limit = asset.get('size_bytes') or asset.get('max_bytes', 2 * 1024**3)
    temporary = path.with_name(path.name + '.partial')
    if temporary.exists(): raise ScoreError(f'Incomplete download exists; review before retrying: {temporary}')
    request = urllib.request.Request(url, headers={'User-Agent': 'DanceRudiments-motion-import/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('xb') as output:
            if response.status != 200: raise ScoreError(f'Download returned HTTP {response.status}')
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type or 'application/json' in content_type:
                raise ScoreError(f'Download returned {content_type}, not an archive')
            count, next_progress = 0, 64 * 1024**2
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > limit: raise ScoreError('Download exceeds its declared byte budget')
                output.write(block)
                if count >= next_progress:
                    print(json.dumps({'download': asset['cache_path'], 'bytes': count}), flush=True)
                    next_progress += 64 * 1024**2
        digest = verify_archive(temporary, asset)
        temporary.rename(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    result = dict(path=str(path), source_url=url, sha256=digest, byte_length=path.stat().st_size)
    _write_bytes_document(path.with_suffix(path.suffix + '.download.json'),
                          canonical_json(result).encode('ascii'), overwrite=True)
    return result


def slug(value, maximum=60):
    result = re.sub('[^a-z0-9_]+', '_', value.lower()).strip('_') or 'motion'
    if not result[0].isalpha(): result = 'motion_' + result
    return result[:maximum].rstrip('_')


def group_name(asset, member):
    if asset.get('group_by') == 'style': return PurePosixPath(member).stem.split('_')[0]
    if asset.get('group_by') == 'parent': return PurePosixPath(member).parent.name or asset['group']
    return asset['group']


def build(source, cache_root, output_root, *, version='1.0.0', resume=False, max_clips=100):
    from dancerudiments_authoring.bvh_import import parse_bvh, compile_bvh, override_bvh_frame_time, BVHLimits
    preflight(output_root)
    configuration = source.get('conversion', {})
    profile_options = {k: configuration[k] for k in ('unit_scale', 'axis_forward', 'axis_up', 'location_range', 'translation_convention', 'root_offset_policy')
                       if k in configuration}
    timing_options = {k: configuration[k] for k in ('source_bpm', 'source_beat_zero_seconds') if k in configuration}
    builders, offsets, seen, records, failures, duplicates = {}, defaultdict(int), {}, [], [], []
    shards = defaultdict(lambda: 1)
    source_identity = hashlib.sha256(canonical_json(source).encode('ascii')).hexdigest()
    limits = BVHLimits()
    total_bytes = 0
    for asset in source['archives']:
        path = asset_path(asset, cache_root)
        archive_sha = verify_archive(path, asset)
        with zipfile.ZipFile(path) as archive:
            members = sorted((i for i in archive.infolist() if i.filename.lower().endswith('.bvh')
                              and not i.is_dir() and '__MACOSX/' not in i.filename
                              and not PurePosixPath(i.filename).name.startswith('._')), key=lambda i: i.filename)
            for info in members:
                try:
                    if info.file_size > limits.max_file_bytes:
                        raise ScoreError('Source BVH exceeds the per-file import limit')
                    payload = archive.read(info)
                    digest = hashlib.sha256(payload).hexdigest()
                    source_ref = {'archive': asset['cache_path'], 'member': info.filename,
                                  'archive_sha256': archive_sha, 'source_sha256': digest}
                    if asset.get('download_url'):
                        source_ref['download_url'] = asset['download_url']
                    member_source = asset.get('members', {}).get(info.filename, {})
                    if member_source:
                        if member_source.get('sha256') != digest:
                            raise ScoreError('Source member differs from the pinned acquisition record')
                        source_ref['original'] = member_source
                    if digest in seen:
                        duplicates.append(dict(source_ref, same_as=seen[digest])); continue
                    clip = parse_bvh(payload, source_id=source['id'], source_name=info.filename,
                                     **profile_options)
                    del payload
                    if member_source.get('frame_time_override') is not None:
                        correction = member_source['frame_time_override']
                        if not isinstance(correction, dict) or set(correction) != {'frame_time_seconds', 'evidence'}:
                            raise ScoreError('Frame interval correction requires an explicit interval and source evidence')
                        clip = override_bvh_frame_time(clip, **correction)
                    group = group_name(asset, info.filename)
                    name = slug(source['id'], 20) + '_' + slug(PurePosixPath(info.filename).stem, 65) + '_' + digest[:10]
                    profile_hash = clip.profile.fingerprint
                    key = (group, profile_hash)
                    descriptors = []
                    chunks = iter(compile_bvh(clip, name=name, **timing_options))
                    first = next(chunks)
                    previous_offset, previous_shard = offsets[key], shards[key]
                    action_bytes = 0
                    try:
                        if offsets[key] and offsets[key] + first.metadata['chunk_count'] > max_clips:
                            shards[key] += 1
                            offsets[key] = 0
                        shard = shards[key]
                        package_id = slug(source['id'], 20) + '_' + slug(group, 50) + '_' + profile_hash[:10] + f'_{shard:03d}'
                        if package_id not in builders:
                            destination = output_root / package_id / version
                            builders[package_id] = MotionPackageBuilder(destination,
                                package_id=package_id, version=version, title=f'{source["title"]} / {group} / {shard}',
                                profile=clip.profile, license=source['license'],
                                provenance={'source_id': source['id'], 'source_url': source['source_url'],
                                    'source_plan_sha256': source_identity, 'group': group,
                                    'conversion': 'dancerudiments.bvh-import-v1',
                                    'changes': 'Source hierarchy retained; local Euler rotations converted to continuous quaternions; offline resampling to 64-pip float64 Recording; gzip and contiguous bounded chunks. No automatic Rigify retargeting.'},
                                resume=resume)
                        builder = builders[package_id]
                        with builder.atomic_batch():
                            for chunk in chain((first,), chunks):
                                offsets[key] += 1
                                existing = {item['id']: item for item in builder._manifest['clips']}.get(chunk.name)
                                if existing:
                                    if existing.get('metadata', {}).get('source_sha256') != digest:
                                        raise ScoreError('Resume clip identity differs from source')
                                    with MotionPackage(builder.output, cache_size=0) as check: check._asset(existing)
                                    descriptor = existing
                                else:
                                    metadata = {
                                        'timing_kind': 'music' if timing_options.get('source_bpm') is not None else 'time-only',
                                        'source_archive': asset['cache_path'], 'source_member': info.filename,
                                        'source_archive_sha256': archive_sha,
                                        'title': member_source.get('title', PurePosixPath(info.filename).stem), 'group': group,
                                        'motion_category': member_source.get('motion_category', source.get('motion_category', 'general'))}
                                    if member_source:
                                        metadata['original_source'] = member_source
                                    if asset.get('download_url'):
                                        metadata['source_download_url'] = asset['download_url']
                                    descriptor = builder.add_bvh_chunk(chunk, metadata=metadata)
                                descriptors.append({'package_id': package_id, 'clip_id': chunk.name,
                                                    'start_pip': descriptor['start_pip'],
                                                    'sample_count': descriptor['sample_count'],
                                                    'byte_length': descriptor['byte_length']})
                                action_bytes += descriptor['byte_length']
                    except BaseException:
                        offsets[key], shards[key] = previous_offset, previous_shard
                        raise
                    total_bytes += action_bytes
                    record = dict(source_ref, profile_sha256=profile_hash,
                                  original_frame_count=clip.frame_count, duration_seconds=clip.duration_seconds,
                                  channels=len(clip.profile.channels), chunks=descriptors)
                    records.append(record); seen[digest] = info.filename
                    print(json.dumps({'imported': info.filename, 'source': source['id'],
                                      'actions': len(records), 'packages': len(builders),
                                      'chunks': len(descriptors), 'stored_bytes_total': total_bytes}), flush=True)
                except (ScoreError, ValueError, OSError, zipfile.BadZipFile) as exc:
                    failure = dict(archive=asset['cache_path'], member=info.filename, error=str(exc))
                    failures.append(failure)
                    print(json.dumps({'failed': failure}), flush=True)
    packages = []
    for package_id, builder in sorted(builders.items()):
        if not builder._manifest['clips']:
            continue
        manifest = builder.finalize()
        notice = (f'# {manifest["title"]}\n\n'
            f'Source: {source["source_url"]}\n\n'
            f'Licence: {source["license"]["id"]} — {source["license"].get("url", source["source_url"])}\n\n'
            f'{source["license"]["attribution"]}\n\n'
            f'Changes: {manifest["provenance"]["changes"]}\n\n'
            'These files are independent optional data packages. Load only the selected clip for a compatible source skeleton. '
            'A different Rigify or mesh rig requires an explicit retarget mapping. '
            'Time-only recordings use 60 BPM as a seconds coordinate; this is not an observed musical tempo. '
            'Chunks retain absolute pips and cover each complete action on its valid pip grid. They do not loop.\n')
        _write_bytes_document(builder.output / 'README.md', notice.encode('utf-8'), overwrite=True)
        _write_bytes_document(builder.output / 'THIRD_PARTY_NOTICES.md', notice.encode('utf-8'), overwrite=True)
        licence_path = ROOT / source['license']['local_text'] if source['license'].get('local_text') else None
        if licence_path and licence_path.is_file():
            _write_bytes_document(builder.output / 'LICENSE.txt', licence_path.read_bytes(), overwrite=True)
        _write_bytes_document(builder.output / 'SOURCES.json', canonical_json(source).encode('ascii'), overwrite=True)
        packages.append(dict(id=package_id, version=version,
            manifest=f'{package_id}/{version}/manifest.json',
            manifest_sha256=file_hash(builder.output / 'manifest.json'),
            profile_sha256=manifest['profile_sha256'], type_uri=manifest['type_uri'],
            clip_count=len(manifest['clips']),
            compressed_clip_bytes=sum(c['byte_length'] for c in manifest['clips']),
            decoded_clip_bytes=sum(c['decoded_byte_length'] for c in manifest['clips'])))
    report = dict(format='dancerudiments.motion-import-report', schema_version=1,
        source_id=source['id'], source_url=source['source_url'], license=source['license'],
        source_plan_sha256=source_identity, unique_actions=len(records),
        recording_chunks=sum(len(r['chunks']) for r in records), duplicate_files=duplicates,
        source_duration_seconds=sum(r['duration_seconds'] for r in records),
        compressed_clip_bytes=total_bytes, packages=packages, actions=records, failures=failures)
    _write_bytes_document(output_root / f'{source["id"]}-import-report.json',
                          canonical_json(report).encode('ascii'), overwrite=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('download', 'build'))
    parser.add_argument('--plan', type=Path, default=ROOT / 'motion-packages/sources.json')
    parser.add_argument('--sources', nargs='+', required=True)
    parser.add_argument('--cache-root', type=Path, default=ROOT / '.cache/motion-sources')
    parser.add_argument('--output', type=Path, default=ROOT / 'motion-packs')
    parser.add_argument('--version', default='1.0.0')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    sources = {source['id']: source for source in plan['sources']}
    failed = False
    for identifier in args.sources:
        if identifier not in sources: parser.error(f'Unknown reviewed source: {identifier}')
        source = sources[identifier]
        if args.command == 'download':
            for asset in source['archives']: print(json.dumps(download(asset, args.cache_root)), flush=True)
        else:
            report = build(source, args.cache_root, args.output, version=args.version, resume=args.resume)
            print(json.dumps({k: report[k] for k in ('source_id', 'unique_actions', 'recording_chunks',
                                                   'compressed_clip_bytes', 'failures')}), flush=True)
            failed |= bool(report['failures'])
    return 2 if failed else 0


if __name__ == '__main__': raise SystemExit(main())
