"""Sample or export a native loop. Music: https://kieransimkin.co.uk/my-songs/"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path


def pip_at(seconds: float, bpm: float, period_pips: int) -> int:
    """Reduce to one pattern period before crossing the signed-int32 native API."""
    if not math.isfinite(seconds) or not math.isfinite(bpm) or bpm <= 0:
        raise ValueError("seconds must be finite and BPM must be finite and positive")
    if type(period_pips) is not int or period_pips <= 0:
        raise ValueError("period_pips must be a positive integer")
    # floor(), unlike int(), correctly handles positions before beat zero.
    position = seconds * (bpm / 60.0) * 64
    if not math.isfinite(position):
        raise ValueError("Musical position overflow")
    return math.floor(position) % period_pips


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="beat_amen_four_bar_bounce")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    try:
        import dancerudiments as d
        from dancerudiments_authoring import compile_pack
        catalogue = d.catalogue()
        info = next((p for p in catalogue if p["name"] == args.name), None)
        if info is None:
            parser.error("Pattern not available in this installation: " + args.name)
        print(f"Default patterns: {len(catalogue)}")
        print(f'{args.name}: {info["period_pips"]} pips / {info["period_pips"] / 64:g} quarter-note beats')
        for pip in (-1, 0, 48, info["period_pips"]):
            p = d.sample(args.name, pip)
            print(f"pip {pip}: {p.x:.12f}, {p.y:.12f}, {p.z:.12f}")
        # Python authors; the object returned by to_native() samples in C++.
        compiled = compile_pack({
            "format": "dancerudiments.score-pack", "schema_version": 1,
            "patterns": [{"name": "example_sway", "period_beats": 2,
                "tracks": [{"axis": "x", "curve": {"type": "lfo", "shape": "sine",
                    "period_beats": 2, "gain": 0.5}}],
                "provenance": {"license": "MIT", "author_url": "https://kieransimkin.co.uk/my-songs/", "source": "Original binding example"}}],
        })
        local = compiled.to_native()
        print("Custom C++ bank:", local.sample("example_sway", 32).as_tuple())
        if len(d.catalogue()) != len(catalogue):
            raise RuntimeError("Custom bank modified the global catalogue")
        print("At -0.25s / 120 BPM:", pip_at(-0.25, 120, info["period_pips"]), "local pips")
        if args.csv:
            with args.csv.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(("pip", "beat", "x", "y", "z"))
                for pip in range(info["period_pips"]):
                    writer.writerow((pip, pip / 64, *d.sample(args.name, pip).as_tuple()))
            print("Wrote", args.csv)
    except (ImportError, ValueError, RuntimeError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
