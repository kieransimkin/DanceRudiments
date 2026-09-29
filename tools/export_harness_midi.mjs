#!/usr/bin/env node
/** Export the audition library as actual MIDI files. No runtime dependencies. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import './release_demo_assets/beat_player.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.resolve(process.argv[2]||path.join(root,'dist/midi'));
const bpm=process.argv[3]===undefined?null:Number(process.argv[3]);
if(bpm!==null&&(!Number.isFinite(bpm)||bpm<20||bpm>300))throw Error('BPM must be 20–300');
const library=JSON.parse(fs.readFileSync(path.join(root,'harness/beats.json'),'utf8'));
fs.mkdirSync(out,{recursive:true});
const manifest={source_library_sha256:library.sha256,files:[]};
for(const score of library.beats){
  if(!/^[a-z][a-z0-9_]*$/.test(score.id))throw Error('Unsafe beat filename');
  const tempo=bpm??Math.max(20,Math.min(300,score.bpm));
  const result=globalThis.DanceBeat.midiWrite(score,tempo), name=score.id+'.mid';
  fs.writeFileSync(path.join(out,name),result.bytes);
  manifest.files.push({filename:name,title:score.title,bpm:tempo,ppq:result.ppq,
    period_beats:score.period_beats,note_count:score.events.length,score_sha256:score.score_sha256,
    max_timing_error_beats:result.maxTimingErrorBeats,license:score.license,
    provenance:score.provenance||{},sha256:createHash('sha256').update(result.bytes).digest('hex')});
}
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
fs.writeFileSync(path.join(out,'README.txt'),
 'DanceRudiments MIDI audition scores\n\n'+
 'Newly synthesised/encoded note-event studies, not recorded audio. The Amen is a quantised structural interpretation.\n'+
 'Every MIDI includes its tempo, loop-end marker, credits and source transformation notes. See manifest.json for exact sources and PPQ quantisation.\n'+
 'Four Groove MIDI derivatives remain CC BY 4.0, credited to Google LLC / Groove MIDI Dataset and the original paper authors.\n'+
 'All other audition scores are MIT-licensed by Kieran Simkin / DanceRudiments; abstract gesture-to-drum timbres are authored listening interpretations.\n');
console.log(`Exported ${manifest.files.length} MIDI files; ${manifest.files.filter(x=>x.max_timing_error_beats>1e-12).length} required timing quantisation.`);
