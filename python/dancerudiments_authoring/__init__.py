"""DanceRudiments offline authoring; install the C++ extension only for playback."""
from ._validation import ScoreError
from .compiler import compile_pack, compile_score
from .io import emit_cpp, emit_json, load_pack, read_json
from .model import CompiledPack, CompiledPattern

__all__ = ['ScoreError', 'CompiledPattern', 'CompiledPack', 'compile_score', 'compile_pack',
           'emit_cpp', 'emit_json', 'load_pack', 'read_json', 'Recording', 'RecordingClock', 'load_recording', 'write_recording',
           'RigChannel', 'RigProfile', 'load_profile', 'write_profile', 'load_builtin_profile',
           'rigify_catalogue', 'rig_type_uri', 'canonical_type_uri', 'extend_profile',
           'BeatAnchor', 'BeatMap', 'RigCapture', 'load_capture', 'write_capture', 'compile_capture',
           'RigMotion', 'RigMotionPlayer', 'load_rig_motion', 'write_rig_motion',
           'MotionPackage', 'MotionPackageBuilder', 'install_motion_package',
           'export_motion_package', 'discover_motion_packages']

from .recording import Recording, RecordingClock, load_recording, write_recording
from .rigs import (RigChannel, RigProfile, load_profile, write_profile, load_builtin_profile,
                   rigify_catalogue, rig_type_uri, canonical_type_uri, extend_profile)
from .motion_clock import BeatAnchor, BeatMap
from .motion_import import RigCapture, load_capture, write_capture, compile_capture
from .motion import RigMotion, RigMotionPlayer, load_rig_motion, write_rig_motion
from .motion_packages import (MotionPackage, MotionPackageBuilder, install_motion_package,
                              export_motion_package, discover_motion_packages)
