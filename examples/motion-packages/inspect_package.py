"""Inspect one selected package and sample only the chosen clip natively."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python'))
from dancerudiments_authoring import MotionPackage, load_profile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('package', type=Path)
parser.add_argument('--clip')
parser.add_argument('--profile', type=Path, help='Exact profile saved with the target scene')
args = parser.parse_args()
profile = load_profile(args.profile) if args.profile else None
with MotionPackage(args.package, expected_profile=profile) as package:
    for clip in package.catalogue():
        print(clip['id'], clip['start_pip'], clip['sample_count'], clip['byte_length'])
    if args.clip:
        motion = package.load(args.clip)
        player = motion.player()
        print('type:', motion.profile.type_uri)
        print('first native pose by numbered channel:', player.by_channel(player.start_pip))
