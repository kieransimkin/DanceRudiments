#!/usr/bin/env python3
"""Build the main offline harness from the installed native library and saved beats.

Run `python -m pip install .` first. Output is a single HTML document; the JSON
sidecar is for audits and CI, not a browser dependency. clang++/wasm-ld are build
requirements only. No third-party JS, audio samples or network resources.
"""
from __future__ import annotations
import argparse
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import tempfile

from release_demo import ROOT, build_page, native_snapshot
from harness_beats import collect, canonical


def build(output=ROOT/'harness/index.html', version=None, commit=None, compiler='clang++'):
    version = version or importlib.metadata.version('dancerudiments')
    commit = commit or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files = [ROOT/'LICENSE'] + sorted((ROOT/'collections').glob('**/THIRD_PARTY_NOTICES.md')) + sorted((ROOT/'collections').glob('**/sources/*/LICENSE'))
    notices = '\n\n'.join('# '+p.relative_to(ROOT).as_posix()+'\n\n'+p.read_text(encoding='utf-8') for p in files if p.is_file())
    output = Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        page = build_page(native_snapshot(),version,commit,folder,compiler,notices=notices)
        # Generate fully before replacing the previous working visualizer.
        shutil.copyfile(page,output)
        shutil.copyfile(page.with_suffix('.json'),output.with_suffix('.json'))
    (output.parent/'beats.json').write_text(canonical(collect(ROOT))+'\n',encoding='utf-8')
    print(f'Offline pattern visualizer: {output} ({output.stat().st_size:,} bytes)')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'harness/index.html')
    parser.add_argument('--version');parser.add_argument('--commit');parser.add_argument('--compiler',default='clang++')
    a=parser.parse_args()
    try:build(a.output,a.version,a.commit,a.compiler)
    except (OSError,ValueError,ImportError,subprocess.CalledProcessError) as exc:parser.exit(1,str(exc)+'\n')
