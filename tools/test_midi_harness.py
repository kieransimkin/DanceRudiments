#!/usr/bin/env python3
"""Exercise the complete offline MIDI harness in a real Chromium browser."""
from __future__ import annotations
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import wave
from playwright.sync_api import sync_playwright


def test(path, chromium=None, in_memory=False):
    path=Path(path).resolve();checks=[];errors=[];requests=[]
    manifest=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    def check(condition,label):
        if not condition:raise AssertionError(label)
        checks.append(label);print(label,flush=True)
    with sync_playwright() as pw:
        options=dict(headless=True,args=['--no-sandbox','--mute-audio'])
        if chromium:options['executable_path']=chromium
        browser=pw.chromium.launch(**options)
        page=browser.new_page(viewport=dict(width=1440,height=1400))
        page.on('pageerror',lambda e:errors.append(str(e)))
        def deny(route):requests.append(route.request.url);route.abort()
        page.route(re.compile('^https?://'),deny)
        if in_memory:page.set_content(path.read_text(encoding='utf-8'),timeout=60000)
        else:page.goto(path.as_uri(),timeout=60000)
        page.wait_for_function('window.audition && audition.ready',timeout=60000)
        check(page.evaluate('audition.state().count')==manifest['pattern_count'],'Full native movement catalogue available')
        check(page.evaluate('audition.state().beatCount')==manifest['beat_count'],'All MIDI/event scores available')
        check(not page.evaluate('audition.state().running'),'No autoplay')
        check(page.evaluate('audition.state().midi.audioState')=='not-created','No AudioContext until user interaction')
        check(page.evaluate('audition.state().selectedBeat')=='amen_four_bar','Full Amen selected initially')
        page.locator('#related-only').check()
        check(page.locator('#grid .card').count()==16,'All sixteen Amen mappings can be isolated')
        page.locator('#beat-score-details summary').click()
        page.locator('#play').click();page.wait_for_timeout(220)
        state=page.evaluate('audition.state()')
        check(state['running'] and state['midi']['audioState']=='running','User gesture starts the Web Audio clock')
        check(state['midi']['scheduled']>0 and state['midi']['voices']>0,'Actual synthetic drum voices scheduled')
        check(page.evaluate('Math.max(...audition.transport.drumBuffer(38).getChannelData(0))')>.01,'Drum buffer contains non-silent audio')
        check(abs(state['beat']-state['midi']['beat'])<1/64,'Animation and MIDI follow the same output clock')
        page.evaluate('''()=>{window.previousBeat=audition.state().beat;document.getElementById('bpm').value='180';document.getElementById('bpm').onchange();window.tempoPhaseError=Math.abs(audition.state().beat-window.previousBeat);}''')
        check(page.evaluate('window.tempoPhaseError')<.03,'Live tempo change preserves phase')
        check(page.evaluate('audition.state().midi.bpm')==180,'MIDI adopts the animation tempo')
        page.locator('#midi-sound').uncheck();page.wait_for_timeout(70)
        check(page.evaluate('audition.state().running && !audition.state().midi.sound'),'Muting does not stop animation')
        check(page.evaluate('audition.state().midi.activeVoices')==0,'Mute cancels queued voices')
        page.locator('#midi-sound').check();page.wait_for_timeout(80)
        page.locator('#play').click();frozen=page.evaluate('audition.state().beat');page.wait_for_timeout(80)
        check(page.evaluate('audition.state().beat')==frozen,'Pause freezes musical position')
        check(page.evaluate('audition.state().midi.activeVoices')==0,'Pause cancels queued notes')
        page.locator('#back').click()
        check(abs(page.evaluate('audition.state().beat')-(int(frozen*64)-1)/64)<1e-10,'Pip stepping uses exactly 1/64 beat')
        page.evaluate('audition.setBeat(-.25)')
        check(page.evaluate('audition.state().beat')==-.25,'Negative musical positions are preserved')
        page.locator('#beat-select').select_option('ukg_two_step')
        check(page.evaluate('audition.state().midi.bpm')==180,'Changing beat does not reset BPM')
        check(page.evaluate('audition.state().beat')==-.25,'Changing beat does not reset animation phase')
        page.locator('#suggested-bpm').click()
        check(page.evaluate('audition.state().midi.bpm')==page.evaluate('audition.beatMetadata().find(b=>b.id==="ukg_two_step").bpm'),'Suggested BPM changes both clocks explicitly')
        page.evaluate('audition.selectBeat("amen_four_bar")')
        page.locator('#amen-toggle').click()
        check(page.evaluate('audition.state().selectedBeat')=='amen_no_ghosts','Amen ghost-note A/B uses the second complete phrase')
        page.locator('#amen-toggle').click()
        page.locator('#follow-beat').check()
        page.evaluate('audition.compare(["beat_drill_displaced_spring"])')
        check(page.evaluate('audition.state().selectedBeat')=='drill_displaced','Following a compared movement selects its own score')
        check(page.locator('#grid .card').count()==16,'Following updates the matching movement filter')
        page.locator('#follow-beat').uncheck();page.locator('#related-only').uncheck()
        page.locator('#search').fill('groove_a_played')
        page.locator('#grid .use-beat').first.click()
        check(page.evaluate('audition.state().selectedBeat')=='score_groove_a_played','Groove MIDI score reachable from its movement card')
        check(page.evaluate('audition.transport.score.events.some(e=>e.note===46)'),'Recorded open-hat articulation is retained')
        # Every score is validated by the same player and SMF export path.
        result=page.evaluate('''()=>{
          let count=0,notes=0,quantised=0;
          for(const b of audition.beatMetadata()){
            audition.selectBeat(b.id);
            const midi=DanceBeat.midiWrite(b,123), parsed=DanceBeat.midiRead(midi.bytes);
            if(parsed.events.length!==b.events.length)throw Error(b.id+' lost MIDI notes');
            if(Math.abs(parsed.period-b.period)>.5/midi.ppq)throw Error(b.id+' lost loop length');
            if(midi.maxTimingErrorBeats>1e-12)quantised++;
            count++;notes+=b.events.length;
          }return {count,notes,quantised};
        }''')
        check(result['count']==manifest['beat_count'],'Every built-in score selects, exports and reloads as MIDI')
        page.evaluate('audition.selectBeat("amen_four_bar")')
        midi=bytes(page.evaluate('Array.from(audition.midiExport().bytes)'))
        with page.expect_download() as download:
            page.locator('#download-midi').click()
        check(download.value.suggested_filename.endswith('.mid'),'MIDI download creates a .mid file')
        page.locator('#midi-file').set_input_files(dict(name='amen-test.mid',mimeType='audio/midi',buffer=midi))
        page.wait_for_function('audition.state().selectedBeat==="imported_midi"')
        check(page.evaluate('audition.transport.score.period')==16,'Local SMF import retains the full Amen loop')
        page.locator('#midi-file').set_input_files(dict(name='broken.mid',mimeType='audio/midi',buffer=b'not-midi'))
        page.wait_for_function('document.getElementById("status").textContent.includes("valid SMF")')
        check(page.evaluate('audition.state().selectedBeat')=='imported_midi','Malformed MIDI leaves the current score intact')
        # Local audio is an alternate source, never an accidental second drum clock.
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*16000)
        page.locator('#audio-file').set_input_files(dict(name='silence.wav',mimeType='audio/wav',buffer=buffer.getvalue()))
        check(page.locator('#midi-sound').is_disabled(),'Local track disables MIDI sound controls')
        check(not page.evaluate('audition.transport.running'),'Local track pauses the MIDI transport')
        page.evaluate('document.getElementById("clear-audio").click()')
        check(not page.locator('#midi-sound').is_disabled(),'Removing local track restores MIDI controls')
        page.evaluate('audition.selectBeat("amen_four_bar");audition.setBeat(15.9)')
        page.locator('#bpm').fill('300');page.locator('#bpm').dispatch_event('change')
        page.locator('#play').click();page.wait_for_timeout(200)
        check(page.evaluate('audition.state().beat')>16,'Playback crosses a full Amen loop boundary')
        page.evaluate('Object.defineProperty(document,"hidden",{value:true,configurable:true});document.dispatchEvent(new Event("visibilitychange"))')
        check(not page.evaluate('audition.state().running'),'Hidden tab pauses both clocks')
        page.evaluate('Object.defineProperty(document,"hidden",{value:false,configurable:true})')
        # Visually inspect the same tested page, including the main movement cards.
        page.locator('#search').fill('');page.locator('#related-only').check()
        page.locator('#beat-kind').select_option('dance')
        page.evaluate('audition.compare(["beat_amen_four_bar_bounce","beat_amen_four_bar_step","beat_amen_four_bar_orbit","beat_amen_four_bar_glide"])')
        page.locator('#beat-score-details summary').click() # fold details for desktop screenshot
        page.locator('#bpm').fill('136');page.locator('#bpm').dispatch_event('change')
        page.evaluate('audition.setBeat(2.25)');page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(180)
        page.screenshot(path=str(path.with_name(path.stem+'-midi-desktop.png')))
        page.set_viewport_size(dict(width=390,height=844));page.wait_for_timeout(180)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Mobile layout fits the viewport')
        page.screenshot(path=str(path.with_name(path.stem+'-midi-mobile.png')))
        check(not errors,'No browser exceptions')
        check(not requests,'No network requests or external assets')
        browser.close()
    report=dict(checks=checks,check_count=len(checks),load_mode='in-memory' if in_memory else 'file',
                html_sha256=sha256(path.read_bytes()).hexdigest(),midi_roundtrips=result)
    path.with_name(path.stem+'-midi-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('html',type=Path);p.add_argument('--chromium');p.add_argument('--in-memory',action='store_true')
    a=p.parse_args();test(a.html,a.chromium,a.in_memory)
