#!/usr/bin/env python3
"""Checkout entry point for the packaged Blender/Rigify bridge."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from dancerudiments_authoring.blender_bridge import main

if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(arguments))
