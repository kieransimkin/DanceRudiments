"""Rebuild the tiny shared C++ recording accessor embedded by exported harnesses."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'python/dancerudiments_authoring/harness_assets'

def build(compiler='clang++'):
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / 'recording.wasm'
        subprocess.run([compiler, '--target=wasm32', '-std=c++17', '-O2', '-nostdlib',
            '-fno-exceptions', '-fno-rtti', '-I'+str(ROOT/'include'), str(ROOT/'tools/recording_wasm.cpp'),
            '-Wl,--no-entry', '-Wl,--strip-all', '-Wl,--export=table_base', '-Wl,--export=sample_recording',
            '-Wl,--export-memory', '-Wl,--max-memory=536870912', '-o', str(target)], check=True)
        raw = target.read_bytes()
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS/'recording.wasm.b64').write_text(base64.b64encode(raw).decode()+'\n')
    sources = ['tools/recording_wasm.cpp', 'include/dancerudiments/recording_view.hpp']
    manifest = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
    manifest['wasm_sha256'] = hashlib.sha256(raw).hexdigest()
    (ASSETS/'recording.wasm.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__ == '__main__':
    build()
