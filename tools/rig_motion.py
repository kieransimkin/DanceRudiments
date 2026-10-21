#!/usr/bin/env python3
"""Run the packaged rig-motion CLI from a source checkout."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from dancerudiments_authoring.motion_cli import main

if __name__ == '__main__':
    raise SystemExit(main())
