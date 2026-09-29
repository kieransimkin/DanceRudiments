"""Verification policy for committed, canonical authoring artifacts.

Generated-collection playback uses the committed C++ table values.
Re-evaluating Python/libm recipes on a different host is a separate numerical comparison. Portable mode
is check-only: it never rounds, rewrites, re-hashes or unlocks shipped data.
"""
from __future__ import annotations

from hashlib import sha256
import math
import os
from pathlib import Path
from typing import Any

from ._validation import canonical_json
from .compiler import compile_pack
from .io import load_pack, read_json
from .model import CompiledPack

ENVIRONMENT_VARIABLE = 'DANCERUDIMENTS_REGENERATION_CHECK'
# 20 units of the 12-decimal authoring grid. Absolute tolerance only: values in
# position tables are dimensionless, not timestamps or sample indices.
PORTABLE_ABS_TOL = 2e-11


def portable_checks() -> bool:
    mode = os.environ.get(ENVIRONMENT_VARIABLE, 'exact')
    if mode not in ('exact', 'portable'):
        raise ValueError(f'{ENVIRONMENT_VARIABLE} must be exact or portable, not {mode!r}')
    return mode == 'portable'


def assert_rebuild_equal(actual: Any, expected: Any, path: str = '$') -> None:
    """Compare JSON structures, allowing only tiny finite float drift in portable mode.

    Names, structure, list order, integer counts, rational-beat strings, hashes,
    licences and other text must match exactly. No digest field is ignored.
    Reports the first changed path rather than a multi-megabyte unittest diff.
    """
    tolerance = PORTABLE_ABS_TOL if portable_checks() else 0.0

    def visit(a: Any, b: Any, location: str) -> None:
        if type(a) is float and type(b) is float:
            if not math.isfinite(a) or not math.isfinite(b):
                raise ValueError(f'{location}: non-finite number in regeneration check')
            if abs(a - b) > tolerance:
                raise ValueError(f'{location}: {a!r} != {b!r}; '
                                 f'absolute difference {abs(a-b):.17g} > {tolerance:g}')
            return
        # Python tuples and JSON arrays have identical serialization semantics.
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if len(a) != len(b):
                raise ValueError(f'{location}: array length {len(a)} != {len(b)}')
            for i, (av, bv) in enumerate(zip(a, b)):
                visit(av, bv, f'{location}[{i}]')
            return
        if type(a) is dict and type(b) is dict:
            if a.keys() != b.keys():
                raise ValueError(f'{location}: object keys differ')
            for key in b:
                visit(a[key], b[key], f'{location}.{key}')
            return
        # bool is not an int here, and integers never receive a float tolerance.
        if type(a) is not type(b) or a != b:
            raise ValueError(f'{location}: exact value/type mismatch: {a!r} != {b!r}')

    visit(actual, expected, path)


def _locked_pack(root: Path, collection: str) -> CompiledPack:
    relative = f'python/dancerudiments_authoring/packs/{collection}.json'
    pack = load_pack(root / relative)
    lock = read_json(root / 'collections/defaults.json')
    if lock.get('format') != 'dancerudiments.default-selection' or lock.get('schema_version') != 2:
        raise ValueError('Unsupported default-selection lock')
    entries = [entry for entry in lock['collections'] if entry['pack'] == relative]
    if len(entries) != 1:
        raise ValueError(f'{collection}: expected one committed default-selection lock')
    digest = sha256(canonical_json(pack.to_dict()).encode('utf-8')).hexdigest()
    if entries[0]['pack_sha256'] != digest:
        raise ValueError(f'{collection}: committed pack fails its exact SHA-256 lock')
    return pack


def checked_score(score: dict, root: Path, collection: str,
                  check: bool) -> tuple[dict, CompiledPack]:
    """Compile normally; in portable CHECKS verify recipes then use locked artifacts.

    First compare freshly evaluated recipes with the committed score. Then
    independently recompile that committed score and compare every field with
    the locked pack. Only after both checks succeed may downstream exact C++,
    HTML, manifest and WASM checks use the unchanged canonical score and pack.
    Write-mode always uses the freshly generated values, regardless of policy.
    """
    if not (check and portable_checks()):
        return score, compile_pack(score)
    saved = read_json(root / f'collections/{collection}/{collection}.score.json')
    assert_rebuild_equal(score, saved, f'{collection}.recipe')
    reference = _locked_pack(root, collection)
    rebuilt = compile_pack(saved)
    assert_rebuild_equal(rebuilt.to_dict(), reference.to_dict(), f'{collection}.compiled')
    print(f'{collection}: portable numerical rebuild verified; exact locked artifacts retained')
    return saved, reference


def checked_compiled_pack(pack: CompiledPack, root: Path, collection: str,
                          check: bool) -> CompiledPack:
    """Equivalent check for directly baked recipes such as Dancefloor 06."""
    if not (check and portable_checks()):
        return pack
    reference = _locked_pack(root, collection)
    assert_rebuild_equal(pack.to_dict(), reference.to_dict(), f'{collection}.compiled')
    print(f'{collection}: portable numerical rebuild verified; exact locked artifacts retained')
    return reference
