"""Optional bundled collections. Importing this module does not load C++ or data."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from .io import load_pack
from .model import CompiledPack


def initial_pack(names: Optional[Iterable[str]] = None) -> CompiledPack:
    """Load all audition candidates, or a nonempty named subset in catalogue order.

    Existing built-ins are not modified. Call .to_native() for C++ playback.
    Source attribution and licence metadata survive selection unchanged.
    """
    pack = load_pack(Path(__file__).parent / 'packs' / 'initial.json')
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
