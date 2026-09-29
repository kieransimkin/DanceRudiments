#!/usr/bin/env python3
"""Build/check Expansion 02. Standard library only; no native build or network."""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from dancerudiments_authoring import emit_cpp, emit_json
from dancerudiments_authoring._reproducibility import checked_score


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def build(check=False):
    source = ROOT / 'collections/expansion/definitions.py'
    spec = importlib.util.spec_from_file_location('expansion_definitions', source)
    definitions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(definitions)
    score = definitions.document()
    score, pack = checked_score(score, ROOT, "expansion", check)
    if len(pack.patterns) != 24:
        raise ValueError('Expansion 02 must contain exactly 24 patterns')
    for p in pack.patterns:
        if p.diagnostics['warnings']:
            raise ValueError(f'{p.name}: {p.diagnostics["warnings"]}')
    manifest = dict(collection_id=definitions.COLLECTION_ID, pattern_count=len(pack.patterns),
                    sample_count=sum(p.period_pips for p in pack.patterns),
                    pack_sha256=sha256(compact(pack.to_dict()).encode()).hexdigest(),
                    definitions_sha256=sha256(source.read_bytes()).hexdigest(),
                    names=[p.name for p in pack.patterns], license='MIT')
    outputs = {
        'collections/expansion/expansion.score.json': json.dumps(score, indent=2, sort_keys=True, allow_nan=False)+'\n',
        'python/dancerudiments_authoring/packs/expansion.json': emit_json(pack),
        'include/dancerudiments/collections/expansion.hpp': emit_cpp(pack, 'dancerudiments_expansion'),
        'collections/expansion/manifest.json': json.dumps(manifest, indent=2, sort_keys=True)+'\n',
    }
    for name, text in outputs.items():
        dest = ROOT / name
        if check:
            if not dest.is_file() or dest.read_text(encoding='utf-8') != text:
                raise ValueError('Missing/stale generated file: '+name)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
    print(('Checked' if check else 'Built') + f' 24 new patterns; {manifest["sample_count"]} samples; ' + manifest['pack_sha256'])
    return pack


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        build(args.check)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, str(exc)+'\n')
