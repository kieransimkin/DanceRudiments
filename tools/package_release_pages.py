#!/usr/bin/env python3
"""Assemble, seal and verify the exact tagged visualizer and mesh-demo site.

This tool never publishes, changes repository settings or downloads motion.
The release workflow performs those explicitly scoped operations separately.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen
import zipfile


FORMAT = 'dancerudiments.release-pages'
QA_FORMAT = 'dancerudiments.mesh-demo-browser-verification'
SCENE_IDS = frozenset(('boxbot', 'prism'))
NAV = '<nav aria-label="More DanceRudiments demos"><a id="mesh-demos-link" href="meshes/">Explore the 3D mesh dance demos</a></nav>'
MAX_SITE_BYTES = 512 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n'


def identity(version, commit):
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('version must be MAJOR.MINOR.PATCH')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('commit must be the complete lowercase Git commit SHA')


def preflight(parent):
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='release-pages-probe-', dir=parent) as temp:
        probe = Path(temp) / 'probe'
        probe.write_bytes(b'ready')
        if probe.read_bytes() != b'ready':
            raise OSError('Temporary file readback failed')
        probe.rename(probe.with_name('renamed'))
        probe.with_name('renamed').unlink()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(canonical(value), encoding='ascii')
    temporary.replace(path)


def file_identity(path, relative):
    digest = sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
            if size > MAX_SITE_BYTES:
                raise ValueError(f'Site asset exceeds size limit: {relative}')
    return dict(path=relative, byte_length=size, sha256=digest.hexdigest())


def site_files(root):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Pages artifacts must not contain symlinks: {path}')
        if path.is_file():
            files.append(path)
    if sum(path.stat().st_size for path in files) > MAX_SITE_BYTES:
        raise ValueError('Combined demo site exceeds the bounded artifact size')
    return files


def prepare(visualizer, pages_dir, version, commit):
    identity(version, commit)
    visualizer = Path(visualizer).resolve()
    pages = Path(pages_dir).resolve()
    if visualizer.is_relative_to(pages):
        raise ValueError('The original visualizer must be outside the generated site')
    metadata = json.loads(visualizer.with_suffix('.json').read_text(encoding='utf-8'))
    html = visualizer.read_bytes()
    if metadata.get('version') != version or metadata.get('source_commit') != commit:
        raise ValueError('Visualizer metadata does not match the requested release identity')
    if sha256(html).hexdigest() != metadata.get('html_sha256'):
        raise ValueError('Visualizer HTML differs from its tested manifest')
    if html.count(b'</header>') != 1 or b'id="mesh-demos-link"' in html:
        raise ValueError('Expected one unchanged visualizer header for the mesh navigation link')
    preflight(pages)
    # Keep every native table and script byte untouched; add only an HTML link.
    result = html.replace(b'</header>', NAV.encode('ascii') + b'\n</header>', 1)
    (pages / 'index.html').write_bytes(result)
    metadata['source_html_sha256'] = metadata['html_sha256']
    metadata['html_sha256'] = sha256(result).hexdigest()
    metadata['mesh_demo_route'] = 'meshes/'
    write_json(pages / 'index.json', metadata)
    (pages / '.nojekyll').write_bytes(b'')
    return pages


def archive(path, root, files):
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for item in files:
                info = zipfile.ZipInfo(item.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                with item.open('rb') as source, output.open(info, 'w') as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def seal(pages_dir, output_dir, qa_report, version, commit):
    identity(version, commit)
    pages, output = Path(pages_dir).resolve(), Path(output_dir).resolve()
    if output == pages or output.is_relative_to(pages) or pages.is_relative_to(output):
        raise ValueError('Release attachments and the Pages tree must be separate directories')
    metadata = json.loads((pages / 'index.json').read_text(encoding='utf-8'))
    if metadata.get('version') != version or metadata.get('source_commit') != commit:
        raise ValueError('Site visualizer identity mismatch')
    if file_identity(pages / 'index.html', 'index.html')['sha256'] != metadata.get('html_sha256'):
        raise ValueError('Prepared visualizer changed before sealing')
    required = ('index.html', 'app.js', 'style.css', 'recording.wasm', 'catalogue.json', 'build.json')
    for name in required:
        if not (pages / 'meshes' / name).is_file():
            raise ValueError(f'Missing mesh-gallery asset: {name}')
    build = json.loads((pages / 'meshes/build.json').read_text(encoding='utf-8'))
    catalogue = json.loads((pages / 'meshes/catalogue.json').read_text(encoding='utf-8'))
    catalogue_scenes = catalogue.get('scenes')
    if (build.get('format') != 'dancerudiments.mesh-demo-build' or build.get('schema_version') != 1
            or build.get('version') != version or build.get('commit') != commit
            or build.get('sceneIds') != ['boxbot', 'prism']
            or catalogue.get('format') != 'dancerudiments.mesh-demo-catalogue'
            or catalogue.get('schema_version') != 1 or not isinstance(catalogue_scenes, list)
            or len(catalogue_scenes) != 2
            or {item.get('id') for item in catalogue_scenes if isinstance(item, dict)} != SCENE_IDS):
        raise ValueError('Expected both named mesh scenes built for this exact release')
    qa = json.loads(Path(qa_report).read_text(encoding='utf-8'))
    if (qa.get('format') != QA_FORMAT or qa.get('schema_version') != 1
            or qa.get('status') != 'PASS' or qa.get('scope') != 'complete-site'
            or qa.get('version') != version or qa.get('source_commit') != commit):
        raise ValueError('A passing mesh browser report for this exact release is required')
    if (not isinstance(qa.get('scenes'), list) or len(qa['scenes']) != 2
            or {item.get('id') for item in qa['scenes'] if isinstance(item, dict)} != SCENE_IDS):
        raise ValueError('Browser verification must cover the distinct boxbot and prism mesh scenes')
    # The QA report binds all tested mesh bytes. A changed script or recording
    # must be tested again, even when the human-readable version is unchanged.
    checked = qa.get('tested_assets')
    if not isinstance(checked, list) or not checked:
        raise ValueError('Browser report has no tested asset hashes')
    for item in checked:
        relative = safe_relative(item.get('path'))
        candidate = pages / relative
        if not candidate.is_file() or candidate.is_symlink() or not candidate.resolve().is_relative_to(pages):
            raise ValueError(f'Tested asset no longer exists inside the site: {relative}')
        if file_identity(candidate, relative) != item:
            raise ValueError(f'Tested asset changed after browser verification: {relative}')
    tested_paths = {item['path'] for item in checked}
    current_paths = {p.relative_to(pages).as_posix() for p in site_files(pages)
                     if p not in (pages / 'site-manifest.json', pages / 'meshes/validation.json')}
    if tested_paths != current_paths:
        raise ValueError('Browser report must bind the entire current site, including both mesh packages')
    preflight(output)
    write_json(pages / 'meshes/validation.json', qa)
    files = [p for p in site_files(pages) if p.name != 'site-manifest.json' or p.parent != pages]
    assets = [file_identity(p, p.relative_to(pages).as_posix()) for p in files]
    manifest = dict(format=FORMAT, schema_version=1, version=version, source_commit=commit,
                    routes=dict(visualizer='./', meshes='meshes/'),
                    browser_validation='meshes/validation.json', files=assets,
                    total_byte_length=sum(item['byte_length'] for item in assets))
    write_json(pages / 'site-manifest.json', manifest)
    prefix = f'DanceRudiments-pages-v{version}'
    mesh_prefix = f'DanceRudiments-mesh-demos-v{version}'
    write_json(output / (prefix + '.json'), manifest)
    archive(output / (prefix + '.zip'), pages, site_files(pages))
    archive(output / (mesh_prefix + '.zip'), pages, site_files(pages / 'meshes'))
    attachments = [output / (prefix + '.json'), output / (prefix + '.zip'), output / (mesh_prefix + '.zip')]
    (output / (prefix + '.sha256')).write_text(''.join(
        file_identity(p, p.name)['sha256'] + '  ' + p.name + '\n' for p in attachments), encoding='ascii')
    evidence = sorted(p for p in output.glob(mesh_prefix + '*') if p.is_file() and not p.name.endswith('.sha256'))
    (output / (mesh_prefix + '.sha256')).write_text(''.join(
        file_identity(p, p.name)['sha256'] + '  ' + p.name + '\n' for p in evidence), encoding='ascii')
    return manifest


def safe_relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/'))
            or any(ord(c) < 32 for c in value)):
        raise ValueError('Manifest asset paths must be safe relative POSIX paths')
    return PurePosixPath(value).as_posix()


def verify(base_url, manifest_path, report_path=None, attempts=1, retry_seconds=5):
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('format') != FORMAT or manifest.get('schema_version') != 1:
        raise ValueError('Expected a release Pages manifest')
    identity(manifest.get('version'), manifest.get('source_commit'))
    parsed = urlsplit(base_url)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Site URL must be an HTTP(S) base URL without credentials/query/fragment')
    if not 1 <= attempts <= 30 or not 0 <= retry_seconds <= 30:
        raise ValueError('Retry limits are out of bounds')
    base_url = base_url.rstrip('/') + '/'
    # .nojekyll is deployment metadata; hosts need not expose it as a public URL.
    files = [item for item in manifest['files'] if item['path'] != '.nojekyll']
    files += [dict(path='site-manifest.json', byte_length=len(manifest_bytes), sha256=sha256(manifest_bytes).hexdigest())]
    if len(files) > 2048 or sum(item['byte_length'] for item in files) > MAX_SITE_BYTES:
        raise ValueError('Manifest exceeds the bounded site size')
    for attempt in range(attempts):
        try:
            verified = []
            for item in files:
                relative = safe_relative(item['path'])
                route = {'index.html': '', 'meshes/index.html': 'meshes/'}.get(relative, relative)
                request = Request(urljoin(base_url, quote(route, safe='/')),
                                  headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity',
                                           'User-Agent': 'DanceRudiments-release-verifier/1'})
                digest, size = sha256(), 0
                with urlopen(request, timeout=30) as response:
                    if response.status != 200:
                        raise ValueError(f'Unexpected HTTP response for {relative}: {response.status}')
                    if relative.endswith('.gz') and response.headers.get('Content-Encoding', 'identity').lower().strip() not in ('', 'identity'):
                        raise ValueError(f'Precompressed package must have identity Content-Encoding for browser integrity: {relative}')
                    for block in iter(lambda: response.read(1024 * 1024), b''):
                        size += len(block)
                        if size > item['byte_length']:
                            raise ValueError(f'Deployed asset is larger than expected: {relative}')
                        digest.update(block)
                if size != item['byte_length'] or digest.hexdigest() != item['sha256']:
                    raise ValueError(f'Deployed bytes differ from the tested artifact: {relative}')
                verified.append(relative)
            result = dict(status='PASS', version=manifest['version'], source_commit=manifest['source_commit'],
                          base_url=base_url, file_count=len(verified), files=verified,
                          manifest_sha256=sha256(manifest_bytes).hexdigest())
            if report_path:
                report = Path(report_path)
                preflight(report.parent)
                write_json(report, result)
            return result
        except (ValueError, HTTPError, URLError, OSError):
            if attempt + 1 == attempts:
                raise
            time.sleep(retry_seconds)
    raise AssertionError('Unreachable retry state')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'seal'):
        command = commands.add_parser(name)
        command.add_argument('--pages-dir', type=Path, default=Path('dist/pages'))
        command.add_argument('--version', required=True)
        command.add_argument('--commit', required=True)
        if name == 'prepare':
            command.add_argument('--visualizer', type=Path, required=True)
        else:
            command.add_argument('--output-dir', type=Path, default=Path('dist/demo'))
            command.add_argument('--qa-report', type=Path, required=True)
    command = commands.add_parser('verify')
    command.add_argument('--url', required=True)
    command.add_argument('--manifest', type=Path, required=True)
    command.add_argument('--report', type=Path)
    command.add_argument('--attempts', type=int, default=1)
    command.add_argument('--retry-seconds', type=int, default=5)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = str(prepare(args.visualizer, args.pages_dir, args.version, args.commit))
    elif args.command == 'seal':
        result = seal(args.pages_dir, args.output_dir, args.qa_report, args.version, args.commit)
        result = dict(status='PASS', version=result['version'], files=len(result['files']), total_byte_length=result['total_byte_length'])
    else:
        result = verify(args.url, args.manifest, args.report, args.attempts, args.retry_seconds)
    print(canonical(result))


if __name__ == '__main__':
    main()
