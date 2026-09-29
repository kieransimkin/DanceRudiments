"""Bundled authoring data for the approved default collection. Importing this module does not load C++ or data."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from .io import load_pack
from .model import CompiledPack


def initial_pack(names: Optional[Iterable[str]] = None) -> CompiledPack:
    """Load the approved initial collection data, or a nonempty named subset in catalogue order.

    These patterns are already defaults; .to_native() remains idempotent.
    Editing one requires a new name: built-ins cannot be overridden.
    Source attribution and licence metadata survive selection unchanged.
    """
    return _select_pack('initial.json', names)


def expansion_pack(names: Optional[Iterable[str]] = None) -> CompiledPack:
    """Load Expansion 02 data. Its 24 motions are native defaults already."""
    return _select_pack('expansion.json', names)


def _select_pack(filename: str, names: Optional[Iterable[str]]) -> CompiledPack:
    pack = load_pack(Path(__file__).parent / 'packs' / filename)
    if names is None:
        return pack
    if isinstance(names, (str, bytes)):
        raise ValueError('names must be an iterable of pattern names, not a string')
    names = list(names)
    if not names or any(not isinstance(n, str) for n in names) or len(names) != len(set(names)):
        raise ValueError('Select one or more unique pattern names')
    unknown = set(names) - {p.name for p in pack.patterns}
    if unknown:
        raise ValueError('Unknown patterns: ' + ', '.join(sorted(unknown)))
    return CompiledPack(tuple(p for p in pack.patterns if p.name in names))
