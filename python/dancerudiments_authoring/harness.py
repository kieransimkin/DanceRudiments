"""Official visualizer export: shared release UI, C++/WASM playback, no JS fallback."""
from __future__ import annotations
from array import array
import base64
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path
import sys

from ._validation import canonical_json, ScoreError
from .recording import Recording

HARNESS_DISPLAY_API_VERSION = 1
DISPLAY_MODES = ('xy', 'bars')

ASSETS = Path(__file__).with_name('harness_assets')
MAX_HARNESS_BYTES = 128 * 1024 * 1024


def render_template(payload):
    if payload.get('recording_mode'):
        note = ('BPM-synchronised audio-derived recordings; not full-body choreography. '
                'Tempo and beat origin are retained from extraction. Recordings do not loop.')
    elif payload.get('source_kind') == 'native-default-catalogue':
        note = ('All movements in this native catalogue. MIDI beats and animations share one tempo. '
                'Personal review choices do not change the library.')
    else:
        note = ('Preview assembled from a retained native-export snapshot; not a fresh native build. '
                'MIDI beats and animations share one tempo.')
    page = (ASSETS/'template.html').read_text(encoding='utf-8')
    for key, value in [('__VERSION__', payload['version']), ('__COUNT__', str(len(payload['pack']['patterns']))),
                       ('__COMMIT__', payload['source_commit']), ('__BUILD_NOTE__', note)]:
        page = page.replace(key, html.escape(value))
    for key, filename in [('/*__STYLE__*/', 'style.css'), ('/*__BEAT_PLAYER__*/', 'beat_player.js'), ('/*__APP__*/', 'app.js')]:
        page = page.replace(key, (ASSETS/filename).read_text(encoding='utf-8'))
    return page.replace('__PAYLOAD__', canonical_json(payload).replace('<', '\\u003c'))


def build_recording_harness(recordings, output, *, collection_id='audio-recordings',
                             audio=None, notices='', download_links=True):
    """Consume recordings one at a time; deduplicate identical float64 columns.

    Uses the SAME packaged HTML/CSS/JS as the catalogue/release visualizer.
    The bundled tiny WASM accessor is built from recording_view.hpp. No compiler
    or network access is needed at export time. A larger recording is projected
    onto any chosen X/Y/Z axes; the full data and download retain every dimension.
    """
    output = Path(output)
    if output.exists() or output.with_suffix('.json').exists():
        raise FileExistsError('Choose new HTML and audit filenames')
    wasm = base64.b64decode((ASSETS/'recording.wasm.b64').read_text().strip(), validate=True)
    built = json.loads((ASSETS/'recording.wasm.json').read_text())
    if hashlib.sha256(wasm).hexdigest() != built['wasm_sha256']:
        raise ScoreError('Packaged recording sampler failed its checksum')
    blob = bytearray()
    pool = {}
    patterns = []
    seen = set()
    clock = None
    count = None
    for recording in recordings:
        if not isinstance(recording, Recording):
            raise ScoreError('Expected validated Recording objects')
        if recording.name in seen or len(seen) >= 1024:
            raise ScoreError('Duplicate recording or more than 1024 candidates')
        seen.add(recording.name)
        if clock is None:
            clock, count = recording.clock, len(recording.samples)
        elif recording.clock != clock or len(recording.samples) != count:
            raise ScoreError('Comparison candidates must share the exact clock and captured extent')
        offsets, hashes = [], []
        for axis in range(len(recording.dimensions)):
            column = array('d', (row[axis] + 0.0 for row in recording.samples))
            if column.itemsize != 8:
                raise ScoreError('Recording export requires binary64 doubles')
            if sys.byteorder != 'little':
                column.byteswap()
            raw = column.tobytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest not in pool:
                if len(blob) + len(raw) > MAX_HARNESS_BYTES:
                    raise ScoreError('Harness exceeds 128 MiB unique sample data; shorten the excerpt or batch')
                pool[digest] = len(blob)
                blob.extend(raw)
            offsets.append(pool[digest])
            hashes.append(digest)
        provenance = dict(recording.provenance)
        provenance.setdefault('title', recording.name.replace('_', ' '))
        provenance.setdefault('family', 'Audio-derived')
        provenance.setdefault('author', 'Kieran Simkin / StemLab')
        provenance.setdefault('license', 'Source audio rights apply')
        provenance['collection_id'] = collection_id
        descriptor = dict(name=recording.name, period_pips=count, start_pip=clock.start_pip,
                          dimensions=list(recording.dimensions), column_offsets=offsets,
                          column_sha256=hashes, provenance=provenance,
                          description=provenance.get('description', 'Audio amplitude envelopes on one BPM clock'),
                          diagnostics={'looping': False},
                          recording_path=('recordings/'+recording.name+'.json' if download_links and
                                          (output.parent/'recordings'/(recording.name+'.json')).is_file() else None))
        descriptor['source_sha256'] = hashlib.sha256(canonical_json([asdict(clock), descriptor]).encode()).hexdigest()
        patterns.append(descriptor)
    if not patterns:
        raise ScoreError('Cannot build an empty comparison')
    audio = dict(audio or {})
    if audio.get('relative_path') and (Path(audio['relative_path']).name != audio['relative_path'] or ':' in audio['relative_path']):
        raise ScoreError('Audio link must be a plain local filename')
    pack = dict(format='dancerudiments.recording-snapshot', schema_version=1, pips_per_beat=64,
                sample_dtype='float64', clock=asdict(clock), patterns=patterns)
    payload = dict(collection_id=collection_id, version='recordings', source_commit='audio-export',
                   source_kind='audio-derived-recordings', recording_mode=True, clock=asdict(clock),
                   audio=audio, pack=pack, pack_sha256=hashlib.sha256(canonical_json(pack).encode()).hexdigest(),
                   beat_library={'beats': [], 'pattern_beats': {}, 'sources': {}}, score={'patterns': []},
                   wasm=base64.b64encode(wasm).decode(), recording_data=base64.b64encode(blob).decode(),
                   notices=notices or 'Audio is private unless you choose to share the output. Source permissions remain applicable.')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    page = render_template(payload)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(page)
    report = dict(format='dancerudiments.recording-harness-report', schema_version=1,
                  candidates=len(patterns), unique_columns=len(pool), sample_bytes=len(blob),
                  clock=asdict(clock), pack_sha256=payload['pack_sha256'], wasm_sha256=built['wasm_sha256'],
                  html_sha256=hashlib.sha256(page.encode()).hexdigest(), native_engine='C++/WebAssembly',
                  renderer='shared DanceRudiments release visualizer', display_modes=list(DISPLAY_MODES), audio_included=bool(audio.get('relative_path')))
    output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
