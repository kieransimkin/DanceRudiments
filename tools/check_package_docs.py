#!/usr/bin/env python3
"""Check author links and usage assets in source and real package archives.

Music: https://kieransimkin.co.uk/my-songs/
Reads archives without extracting or executing them. No network required.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile

MUSIC_URL = 'https://kieransimkin.co.uk/my-songs/'
ROOT = Path(__file__).resolve().parents[1]
IMAGES = ('visualizer-amen-desktop.png', 'visualizer-midi-score.png', 'visualizer-mobile.png')
BRANDING = ('logo.svg', 'logo-monochrome.svg', 'logo.png', 'README.md')


def require_link(text: str, label: str) -> None:
    if MUSIC_URL not in text:
        raise ValueError(f'{label}: missing author music link')


def check_source(root: Path = ROOT) -> None:
    for name in ('README.md', 'AUTHORS.md', 'pyproject.toml', 'package.json',
                 'package-lock.json', 'CMakeLists.txt', 'conanfile.py',
                 'packaging/CPP_BINARY_README.md', 'docs/bindings.md'):
        require_link((root / name).read_text(encoding='utf-8'), name)
    package = json.loads((root / 'package.json').read_text(encoding='utf-8'))
    if package['homepage'] != MUSIC_URL or package['author']['url'] != MUSIC_URL:
        raise ValueError('npm author/homepage differ from the canonical music URL')
    require_link(package['description'], 'npm description')
    for path in (root / 'collections').glob('*/README.md'):
        require_link(path.read_text(encoding='utf-8'), str(path))
    for image in IMAGES:
        if not (root / 'docs/images' / image).is_file():
            raise ValueError(f'Missing README screenshot: {image}')
    for filename in BRANDING:
        if not (root / 'docs/branding' / filename).is_file():
            raise ValueError(f'Missing branding file: {filename}')
    require_link((root / 'docs/branding/README.md').read_text(encoding='utf-8'), 'docs/branding/README.md')
    for family in ('atlas', 'continuum', 'club', 'dancefloor'):
        require_link((root / f'tools/build_{family}_collection.py').read_text(encoding='utf-8'), family+' README generator')
    print('Source: author metadata, first-party READMEs and screenshots verified')


def check_archive(path: Path) -> None:
    """Check a wheel, source tarball, npm tarball or native release ZIP."""
    path = Path(path)
    if path.suffix in ('.whl', '.zip'):
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if not n.endswith('/')]
            selected = {n: archive.read(n) for n in names if PurePosixPath(n).name.lower() in
                        ('readme.md', 'authors.md', 'package.json', 'pyproject.toml', 'metadata', 'pkg-info', 'package-info.txt')}
    elif path.name.endswith(('.tar.gz', '.tgz')):
        with tarfile.open(path, 'r:gz') as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            names = [m.name for m in members]
            selected = {m.name: archive.extractfile(m).read() for m in members
                        if PurePosixPath(m.name).name.lower() in
                        ('readme.md', 'authors.md', 'package.json', 'pyproject.toml', 'metadata', 'pkg-info', 'package-info.txt')}
    else:
        raise ValueError(f'Unsupported archive: {path}')
    if not any(n.endswith('/README.md') or n == 'README.md' for n in names):
        raise ValueError(f'{path}: no packaged README')
    for suffix in ('AUTHORS.md', 'docs/bindings.md', *('docs/images/'+n for n in IMAGES),
                   *('docs/branding/'+n for n in BRANDING)):
        if not any(n == suffix or n.endswith('/'+suffix) for n in names):
            raise ValueError(f'{path}: missing {suffix}')
    if not any(n.endswith('examples/bindings/python/quickstart.py') for n in names):
        raise ValueError(f'{path}: missing runnable binding examples')
    for name, data in selected.items():
        # Do not relabel third-party source documentation as the project's work.
        if '/sources/' not in name:
            require_link(data.decode('utf-8'), str(path)+':'+name)
    if path.suffix == '.whl' and not any(n.endswith('.dist-info/METADATA') for n in names):
        raise ValueError('Wheel is missing distribution metadata')
    print(f'{path.name}: author links, packaged READMEs, examples and screenshots verified')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        if args.archive:
            for path in args.archive:
                check_archive(path)
        else:
            check_source()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
