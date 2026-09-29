"""Shared validation for authoring and compiled interchange. Standard library only."""
from __future__ import annotations

import json
import math
import re
from fractions import Fraction
from typing import Any, Iterable

PIPS_PER_BEAT = 64
MAX_SAMPLES = 65535
MAX_PACK_SAMPLES = 1048576
MAX_PATTERNS = 1024
BUILTIN_NAMES = frozenset("""bounce sway circle figure_eight step_touch box_step helix
clay_background single_stroke_roll double_stroke_roll multiple_bounce_roll
single_paradiddle flam drag five_stroke_roll""".split())


class ScoreError(ValueError):
    """Invalid score, unsupported data, or unsafe compilation request."""


def fields(value: Any, allowed: Iterable[str], required: Iterable[str], path: str) -> dict:
    if not isinstance(value, dict):
        raise ScoreError(f"{path}: expected an object")
    extra = set(value) - set(allowed)
    missing = set(required) - set(value)
    if extra or missing:
        raise ScoreError(f"{path}: unknown fields {sorted(map(str, extra))}; missing {sorted(missing)}")
    return value


def number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoreError(f"{path}: expected a finite number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ScoreError(f"{path}: invalid number") from exc
    if not math.isfinite(result):
        raise ScoreError(f"{path}: expected a finite number")
    return result


def integer(value: Any, low: int, high: int, path: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ScoreError(f"{path}: expected an integer in [{low}, {high}]")
    return value


def beat(value: Any, path: str) -> Fraction:
    """Decimals mean their decimal spelling; use '1/3', not a float, for triplets."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Fraction)):
        raise ScoreError(f"{path}: expected a beat number or rational string")
    if isinstance(value, float):
        number(value, path)
        value = str(value)
    if isinstance(value, str) and len(value) > 128:
        raise ScoreError(f"{path}: rational value is too long")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ScoreError(f"{path}: invalid beat value {value!r}") from exc
    if result.numerator.bit_length() > 128 or result.denominator.bit_length() > 128:
        raise ScoreError(f"{path}: rational precision exceeds 128 bits")
    return result


def choice(value: Any, allowed: Iterable[str], path: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ScoreError(f"{path}: expected one of {', '.join(allowed)}")
    return value


def text(value: Any, path: str) -> str:
    if not isinstance(value, str) or '\0' in value:
        raise ScoreError(f"{path}: expected a string without NUL characters")
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ScoreError(f"{path}: invalid Unicode") from exc
    return value


def name(value: Any, path: str = 'name') -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,127}', value):
        raise ScoreError(f"{path}: expected [a-z][a-z0-9_]{{0,127}}")
    return value


def sequence(value: Any, low: int, high: int, path: str) -> list:
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ScoreError(f"{path}: expected {low}..{high} items")
    return list(value)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                          allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ScoreError('Metadata/score must be finite, JSON-serializable data') from exc
