#!/usr/bin/env python3
"""Source-checkout entry point: no pip install or native build is required."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from dancerudiments_authoring.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
