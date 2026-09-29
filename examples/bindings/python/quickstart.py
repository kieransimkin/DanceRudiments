"""Run against the installed native extension. Music: https://kieransimkin.co.uk/my-songs/"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import dancerudiments as d


def pip_at(seconds: float, bpm: float, beat_zero: float = 0.0) -> int:
    """Use absolute transport time, floor negative positions, and reject overflow."""
    if not all(math.isfinite(v) for v in (seconds, bpm, beat_zero)) or bpm <= 0:
        raise ValueError("Finite times and a positive BPM are required")
    value = math.floor((seconds - beat_zero) * bpm / 60 * d.PIPS_PER_BEAT)
    if not -(2**31) <= value < 2**31:
        raise OverflowError("pip exceeds the signed 32-bit API")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, help="Optional compiled JSON pack")
    args = parser.parse_args()
    catalogue = d.catalogue()
    info = next((p for p in catalogue if p["name"] == "beat_amen_four_bar_bounce"), None)
    if info is None:
        raise SystemExit("Installed release predates Club 05; build the current checkout.")
    print(f"Python native catalogue: {len(catalogue)} movements")
    print(f"{info['name']}: {info['period_pips'] / d.PIPS_PER_BEAT:g} beats")
    for pip in (-1, 0, 16, 32, 48, 64):
        position = d.sample(info["name"], pip)
        print(f"pip {pip:3d} -> " + ", ".join(f"{v:.6f}" for v in position.as_tuple()))
    # These values are copied into a C++-owned table.
    custom = d.SampledPattern("tutorial_cycle", "Four-pip custom table", [
        (0, 0, 0), (0.5, 0, 0), (0, 0, 0), (-0.5, 0, 0)])
    bank = d.PatternLibrary([custom])
    assert bank.sample("tutorial_cycle", -1).x == -0.5
    assert len(bank.catalogue()) == len(catalogue) + 1
    assert pip_at(-0.001, 120) == -1
    print("Custom table wraps at -1:", bank.sample("tutorial_cycle", -1).as_tuple())
    if args.pack:
        from dancerudiments_authoring import load_pack
        compiled = load_pack(args.pack)
        library = compiled.to_native()
        print("Compiled pack sample:", library.sample(compiled.patterns[0].name, 16).as_tuple())
    print("Music: https://kieransimkin.co.uk/my-songs/")


if __name__ == "__main__":
    main()
