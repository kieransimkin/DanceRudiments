'use strict';
(() => {
  // Decode bounded chunks: Uint8Array.from(atob(...)) can create a huge temporary
  // character array for a multi-megabyte embedded module.
  function decodeBase64(text){
    const padding=text.endsWith('==')?2:text.endsWith('=')?1:0;
    const bytes=new Uint8Array(text.length/4*3-padding);let offset=0;
    for(let start=0;start<text.length;start+=32768){
      const chunk=atob(text.slice(start,start+32768));
      for(let i=0;i<chunk.length;i++)bytes[offset++]=chunk.charCodeAt(i);
    }
    return bytes;
  }
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('data').textContent);
  const patterns = data.pack.patterns;
  let phrasePips = Math.max(...patterns.map(p => p.period_pips));
  $('seek').max = phrasePips - 1;
  const project = v => [v[0]+.25*v[2], v[1]-.2*v[2]];
  const STORAGE = 'dancerudiments-review:' + data.collection_id + ':' + data.pack_sha256;
  const names = new Map(patterns.map((p, i) => [p.name, i]));
  const reviews = new Map(patterns.map(p => [p.name, {status: 'keep', note: ''}]));
  const compared = new Set();
  // The catalogue stays complete in the DOM, but offscreen canvases need not
  // allocate high-DPI backing stores or redraw on every musical-clock frame.
  let renderedLastFrame = 0;
  const visibility = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const plot = entry.target.motionPlot;
      if (!plot) continue;
      plot.visible = entry.isIntersecting;
      if (!plot.visible) {
        plot.background = plot.waveBackground = null;
        plot.stage.width = plot.wave.width = 1;
        plot.stage.height = plot.wave.height = 1;
      }
    }
    dirty = true;
  }, {rootMargin:'160px 0px'});
  let native, plots = [], baseBeat = 0, origin = performance.now(), running = false;
  let bpm = 120, amplitude = .7, dirty = true, audioURL = null, storageOK = true;
  const audio = $('audio');
  const beatLibrary = data.beat_library || {beats:[],pattern_beats:{},sources:{}};
  const beats = new Map(beatLibrary.beats.map(b=>[b.id,DanceBeat.normalizeBeat(b)]));
  let selectedBeat=null, scoreBackground=null, playPending=false;
  const transport = new DanceBeat.BeatTransport({bpm,onChange:()=>{
    if(!audioURL)running=transport.running;
    updatePlay();dirty=true;
  }});
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

  function message(text, error = false) {
    $('status').textContent = text;
    $('status').style.color = error ? '#ffb8b8' : '';
  }
  function reviewDocument() {
    return {format: 'dancerudiments.review', schema_version: 1,
      collection_id: data.collection_id, pack_sha256: data.pack_sha256,
      choices: patterns.map(p => ({name: p.name, source_sha256: p.source_sha256, ...reviews.get(p.name)}))};
  }
  function validateReview(doc) {
    if (!doc || doc.format !== 'dancerudiments.review' || doc.schema_version !== 1 ||
        doc.collection_id !== data.collection_id || doc.pack_sha256 !== data.pack_sha256 ||
        !Array.isArray(doc.choices) || doc.choices.length > patterns.length)
      throw new Error('This review does not match this exact collection revision.');
    const found = new Set(), validated = new Map();
    for (const c of doc.choices) {
      if (!c || !names.has(c.name) || found.has(c.name) ||
          c.source_sha256 !== patterns[names.get(c.name)].source_sha256 ||
          !['unreviewed','keep','maybe','skip'].includes(c.status) ||
          typeof c.note !== 'string' || c.note.length > 2000)
        throw new Error('Invalid, duplicate, or changed review entry. Nothing was imported.');
      found.add(c.name); validated.set(c.name, {status:c.status, note:c.note});
    }
    return validated;
  }
  function importReview(doc) {
    const values = validateReview(doc);
    for (const p of patterns) reviews.set(p.name, values.get(p.name) || {status:'unreviewed',note:''});
    save(); render(); message('Review imported. No pattern data were changed.');
  }
  function save() {
    try { localStorage.setItem(STORAGE, JSON.stringify(reviewDocument())); }
    catch (_) { storageOK=false; message('Browser storage is unavailable. Use Export review to save your choices.',true); }
  }
  try {
    const saved = localStorage.getItem(STORAGE);
    if (saved) {
      for (const [name,value] of validateReview(JSON.parse(saved))) reviews.set(name,value);
    }
  } catch (_) { storageOK=false; }

  function beatNow() {
    if (audioURL) return (audio.currentTime - Number($('offset').value || 0)) * bpm / 60;
    return transport.beat();
  }
  function setBeat(value) {
    if (!Number.isFinite(value)) throw new Error('Beat must be finite');
    if (audioURL) {
      const time = Number($('offset').value || 0) + value*60/bpm;
      if (Number.isFinite(audio.duration)) audio.currentTime=Math.max(0,Math.min(audio.duration,time));
    } else { transport.seek(value); }
    dirty=true;
  }
  function updatePlay() { $('play').textContent=playPending ? 'Starting…' : running ? 'Pause' : 'Play'; $('play').setAttribute('aria-pressed',String(running)); }
  function pause() {
    baseBeat=beatNow(); playPending=false;transport.pause();running=false;audio.pause(); updatePlay();dirty=true;
  }
  async function play() {
    if (!native || playPending || running) return;
    playPending=true;updatePlay();
    try {
      if (audioURL) await audio.play();
      else await transport.play();
    } catch (error) { message(error.message,true); }
    finally {playPending=false;updatePlay();dirty=true;}
  }
  $('play').onclick=() => running || playPending ? pause() : play();
  $('reset').onclick=() => { setBeat(0); dirty=true; };
  $('back').onclick=() => { pause(); setBeat((Math.floor(beatNow()*64+1e-8)-1)/64); };
  $('forward').onclick=() => { pause(); setBeat((Math.floor(beatNow()*64+1e-8)+1)/64); };
  $('bpm').onchange=() => {
    const next=Number($('bpm').value);
    if (!Number.isFinite(next) || next<20 || next>300) { $('bpm').value=bpm; return; }
    bpm=next;transport.setBpm(next);dirty=true;
  };
  $('amplitude').oninput=() => { amplitude=Number($('amplitude').value)/100; $('amp-label').textContent=Math.round(amplitude*100)+'%'; dirty=true; };
  $('trails').onchange=() => { for (const p of plots) p.background=null; dirty=true; };
  $('seek').oninput=() => setBeat(Number($('seek').value)/64);
  $('offset').onchange=() => { if (!Number.isFinite(Number($('offset').value))) $('offset').value=0; dirty=true; };
  audio.addEventListener('play',() => { running=true; updatePlay(); dirty=true; });
  audio.addEventListener('pause',() => { running=false; updatePlay(); dirty=true; });
  audio.addEventListener('ended',() => { running=false; updatePlay(); dirty=true; });
  audio.addEventListener('seeked',() => { dirty=true; });
  audio.addEventListener('error',() => message('This browser could not decode the selected audio file.',true));
  $('audio-file').onchange=() => {
    const file=$('audio-file').files[0]; if (!file) return;
    pause(); if (audioURL) URL.revokeObjectURL(audioURL);
    audioURL=URL.createObjectURL(file); audio.src=audioURL; midiAvailability();
    message('Local audio loaded. Set its BPM and beat-zero offset, then press Play.');
  };
  $('clear-audio').onclick=() => {
    const current=beatNow(); pause();
    if (audioURL) URL.revokeObjectURL(audioURL);
    audioURL=null; audio.removeAttribute('src'); audio.load(); $('audio-file').value='';
    transport.seek(current);midiAvailability();dirty=true;message('Audio removed. MIDI beat and movements use the shared clock.');
  };
  reducedMotion.addEventListener('change', e => { if (e.matches) { pause(); message('Reduced motion enabled. Playback paused; manual stepping remains available.'); } });
  document.addEventListener('visibilitychange',() => { if (document.hidden) pause(); });
  window.addEventListener('resize',() => { scoreBackground=null;dirty=true; });


  function midiAvailability(){
    for(const id of ['beat-select','beat-search','beat-kind','midi-sound','midi-file','suggested-bpm','amen-toggle'])$(id).disabled=!!audioURL;
    $('amen-toggle').disabled=!!audioURL || !['amen_four_bar','amen_no_ghosts'].includes(selectedBeat?.id);
    $('midi-mode').textContent=audioURL?'Local track selected: MIDI playback is paused. Remove the audio file to return to MIDI.':
      `${beatLibrary.beats.length} built-in MIDI/event scores · exact rational source timing · shared animation BPM`;
  }
  function populateBeats(){
    const kind=$('beat-kind').value,q=$('beat-search').value.trim().toLowerCase();
    const list=[...beats.values()].filter(b=>(!kind||b.kind===kind)&&(!q||[b.id,b.title,b.family].join(' ').toLowerCase().includes(q)));
    if(selectedBeat&&!list.some(b=>b.id===selectedBeat.id))list.unshift(selectedBeat);
    $('beat-select').replaceChildren();const groups=new Map();
    for(const b of list){
      const title=(b.kind==='dance'?'Dance / ':b.kind==='groove'?'Recorded groove / ':b.kind==='core'?'Core / ':'Event study / ')+b.family;
      if(!groups.has(title)){const group=node('optgroup');group.label=title;groups.set(title,group);$('beat-select').append(group);}
      const option=node('option','',b.title);option.value=b.id;groups.get(title).append(option);
    }
    if(selectedBeat)$('beat-select').value=selectedBeat.id;
    $('beat-found').textContent=`${list.length} available in this view`;
  }
  function selectBeat(id){
    if(audioURL){message('Remove the local audio track before selecting MIDI playback.',true);return;}
    if(!beats.has(id))throw Error('Unknown beat');
    selectedBeat=beats.get(id);transport.setScore(selectedBeat);
    phrasePips=Math.max(1,Math.round(selectedBeat.period*64));$('seek').max=phrasePips-1;
    $('beat-title').textContent=selectedBeat.title;
    $('beat-notes').textContent=selectedBeat.notes||'';
    $('beat-meta').textContent=`${selectedBeat.period_beats} quarter-note beats per loop · ${selectedBeat.meter?selectedBeat.meter.join('/'):'meter not specified'} · suggested ${Math.round(selectedBeat.bpm)} BPM · ${selectedBeat.events.length} notes`;
    $('amen-toggle').disabled=!['amen_four_bar','amen_no_ghosts'].includes(id);
    $('beat-lanes').replaceChildren();
    for(const lane of [...new Set(selectedBeat.events.map(e=>e.lane))]){
      const label=node('label','lane-switch'),box=node('input');box.type='checkbox';box.checked=true;box.setAttribute('aria-label','Play '+lane);
      box.onchange=()=>{transport.mute(lane,!box.checked);scoreBackground=null;dirty=true;};label.append(box,document.createTextNode(lane));$('beat-lanes').append(label);
    }
    $('beat-sources').onclick=()=>showDetail(selectedBeat.title+' / source',JSON.stringify({
      source_path:selectedBeat.source_path,license:selectedBeat.license,score_sha256:selectedBeat.score_sha256,
      notes:selectedBeat.notes,provenance:selectedBeat.provenance,
      sources:(selectedBeat.reference_ids||[]).map(id=>beatLibrary.sources[id]).filter(Boolean)
    },null,2));
    scoreBackground=null;populateBeats();if($('related-only').checked)render();dirty=true;
  }
  function followBeat(name){const id=beatLibrary.pattern_beats[name];if(id)selectBeat(id);}
  function importMidi(bytes,title){
    const score=DanceBeat.midiRead(bytes,title);beats.set(score.id,score);
    $('beat-kind').value='';$('beat-search').value='';selectBeat(score.id);
    message('MIDI loaded locally. It follows the current animation BPM, not its original tempo map.');return score;
  }
  $('beat-select').onchange=()=>selectBeat($('beat-select').value);
  $('beat-kind').onchange=populateBeats;$('beat-search').oninput=populateBeats;
  $('midi-sound').onchange=()=>transport.setSound($('midi-sound').checked).catch(e=>{pause();message(e.message,true);});
  $('midi-volume').oninput=()=>transport.setVolume(Number($('midi-volume').value)/100);
  $('suggested-bpm').onclick=()=>{if(selectedBeat){$('bpm').value=String(Math.min(300,Math.max(20,selectedBeat.bpm)));$('bpm').onchange();}};
  $('amen-toggle').onclick=()=>selectBeat(selectedBeat.id==='amen_four_bar'?'amen_no_ghosts':'amen_four_bar');
  $('follow-beat').onchange=()=>{if($('follow-beat').checked&&compared.size)followBeat(patterns[[...compared][0]].name);};
  $('related-only').onchange=render;
  $('compare-beat').onclick=()=>{
    const associated=(selectedBeat?.pattern_names||[]).filter(n=>names.has(n)).slice(0,4);
    if(!associated.length){message('This imported beat has no associated built-in movements. Compare any cards manually.');return;}
    compared.clear();associated.forEach(n=>compared.add(names.get(n)));render();$('comparison').scrollIntoView({block:'start'});
  };
  $('midi-file').onchange=async()=>{
    const file=$('midi-file').files[0];if(!file)return;
    try{if(file.size>2097152)throw Error('MIDI exceeds 2 MiB');importMidi(new Uint8Array(await file.arrayBuffer()),file.name);}
    catch(error){message(error.message,true);}
    $('midi-file').value='';
  };
  $('download-midi').onclick=()=>{
    try{
      const result=DanceBeat.midiWrite(selectedBeat,bpm);
      const url=URL.createObjectURL(new Blob([result.bytes],{type:'audio/midi'})),a=node('a');
      a.href=url;a.download='DanceRudiments-'+selectedBeat.id+'-'+Math.round(bpm)+'bpm.mid';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      message(`MIDI exported at ${bpm} BPM / ${result.ppq} PPQ. `+(result.maxTimingErrorBeats>1e-12?
        `Maximum timing quantisation: ${result.maxTimingErrorBeats.toExponential(2)} beats; browser playback retains exact source onsets.`:
        'Onsets fit exactly on the MIDI tick grid. Velocities use MIDI’s 7-bit resolution.'));
    }catch(error){message(error.message,true);}
  };
  $('beat-score-details').ontoggle=()=>{scoreBackground=null;dirty=true;};
  function drawBeatScore(beat){
    if(!selectedBeat||!$('beat-score-details').open)return;
    const canvas=$('beat-score'),parent=canvas.parentElement;
    const lanes=[...new Set(selectedBeat.events.map(e=>e.lane))].slice(0,32);
    const w=Math.min(8192,Math.max(600,parent.clientWidth,selectedBeat.period*45)),h=30+lanes.length*21;
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;canvas.style.width=w+'px';canvas.style.height=h+'px';scoreBackground=null;}
    const left=100,width=w-left-12,ctx=canvas.getContext('2d');
    if(!scoreBackground){
      scoreBackground=document.createElement('canvas');scoreBackground.width=w;scoreBackground.height=h;const g=scoreBackground.getContext('2d');
      g.fillStyle='#111923';g.fillRect(0,0,w,h);g.font='10px system-ui';
      const stride=Math.max(.25,Math.ceil(selectedBeat.period/160)/4);
      for(let b=0;b<=selectedBeat.period;b+=stride){const x=left+b/selectedBeat.period*width;
        g.strokeStyle=Number.isInteger(b)?'#3d4b5d':'#202e3c';g.beginPath();g.moveTo(x,20);g.lineTo(x,h);g.stroke();
        if(Number.isInteger(b)){g.fillStyle='#a8b9c8';g.fillText(String(b+1),x+2,12);}
      }
      lanes.forEach((lane,j)=>{g.fillStyle=transport.muted.has(lane)?'#667080':'#bdcddd';g.fillText(lane.slice(0,17),3,39+j*21);});
      for(const e of selectedBeat.events){const row=lanes.indexOf(e.lane);if(row<0)continue;
        g.globalAlpha=transport.muted.has(e.lane)?.15:.28+.72*e.velocity;g.fillStyle=e.channel!==9?'#bda5fb':e.note===36?'#83e8d0':e.note===38?'#efb37c':'#ddd9a4';
        g.beginPath();g.arc(left+e.time/selectedBeat.period*width,35+row*21,2+2*e.velocity,0,Math.PI*2);g.fill();
      }g.globalAlpha=1;
    }
    ctx.drawImage(scoreBackground,0,0);ctx.strokeStyle='#f8faff';const x=left+DanceBeat.positiveModulo(beat,selectedBeat.period)/selectedBeat.period*width;
    ctx.beginPath();ctx.moveTo(x,18);ctx.lineTo(x,h);ctx.stroke();
    if(running&&(x<parent.scrollLeft+left||x>parent.scrollLeft+parent.clientWidth-20))parent.scrollLeft=Math.max(0,x-parent.clientWidth*.7);
  }
  populateBeats();midiAvailability();
  if(beats.size)selectBeat(beats.has('amen_four_bar')?'amen_four_bar':beats.keys().next().value);

  function node(tag,className,text) {
    const n=document.createElement(tag); if (className) n.className=className;
    if (text !== undefined) n.textContent=text; return n;
  }
  function setStatus(name,status) {
    if (!names.has(name) || !['unreviewed','keep','maybe','skip'].includes(status)) throw new Error('Invalid review choice');
    reviews.get(name).status=status; save(); render();
  }
  function showDetail(title,body) {
    $('detail-title').textContent=title; $('detail-body').textContent=body;
    $('details').showModal();
  }
  $('close-details').onclick=() => $('details').close();
  $('notices').onclick=() => showDetail('Sources & licences',data.notices);
  $('details').addEventListener('click', e => { if (e.target===$('details')) $('details').close(); });

  function card(i,comparison=false) {
    const p=patterns[i], meta=p.provenance;
    const c=node('article','card'); c.dataset.name=p.name;
    const head=node('div','card-head');
    const id=node('div','card-id'); id.append(node('span','',meta.family),node('span','period',(p.period_pips/64)+' beats'));
    head.append(id,node('h3','',meta.title)); c.append(head);
    const stage=node('canvas','stage'), wave=node('canvas','wave');
    stage.setAttribute('aria-label',meta.title+' motion preview');
    wave.setAttribute('aria-label','X, Y and available Z position curves over one cycle');
    c.append(stage,wave);
    const plot={i,stage,wave,background:null,waveBackground:null,amp:-1,visible:false};
    c.motionPlot=plot;plots.push(plot);visibility.observe(c);
    const body=node('div','card-body'); body.append(node('p','desc',p.description));
    if (!comparison) {
      const buttons=node('div','review-buttons');
      for (const [value,label] of [['keep','Keep'],['maybe','Maybe'],['skip','Skip']]) {
        const b=node('button',value,label); b.setAttribute('aria-pressed',reviews.get(p.name).status===value?'true':'false');
        b.onclick=() => setStatus(p.name,reviews.get(p.name).status===value?'unreviewed':value); buttons.append(b);
      }
      body.append(buttons);
    }
    const bottom=node('div','card-bottom');
    const compareLabel=node('label','', ''); const check=node('input'); check.type='checkbox'; check.checked=compared.has(i);
    check.setAttribute('aria-label','Compare '+meta.title);
    check.onchange=() => {
      if (check.checked && compared.size>=4) { check.checked=false; message('Compare up to four candidates at a time.',true); return; }
      check.checked ? compared.add(i) : compared.delete(i); if(check.checked && $('follow-beat').checked)followBeat(p.name);render();
    };
    compareLabel.append(check,document.createTextNode('Compare'));
    const source=node('button','source-button',meta.license+' · Details');
    source.onclick=() => showDetail(meta.title,JSON.stringify({name:p.name,source_sha256:p.source_sha256,
                       provenance:meta,diagnostics:p.diagnostics},null,2));
    bottom.append(compareLabel,source); body.append(bottom);
    const beatId=beatLibrary.pattern_beats[p.name];
    if(beatId && beats.has(beatId)){
      const use=node('button','use-beat','Use this movement’s beat');use.dataset.beat=beatId;
      use.onclick=()=>{selectBeat(beatId);message('Beat selected; BPM and animation phase are unchanged.');};body.append(use);
    }

    if (!comparison) {
      const note=node('input','note'); note.type='text'; note.placeholder='Your note…';note.maxLength=2000;
      note.value=reviews.get(p.name).note; note.setAttribute('aria-label','Note for '+meta.title);
      note.oninput=() => { reviews.get(p.name).note=note.value; save(); };
      body.append(note);
    }
    c.append(body); return c;
  }
  function matches(p) {
    const family=$('family').value, status=$('review').value, search=$('search').value.trim().toLowerCase();
    const collection=$('collection').value;
    return (!$('related-only').checked || selectedBeat?.pattern_names?.includes(p.name)) && (!collection || (p.provenance.collection_id || 'core')===collection) && (!family || p.provenance.family===family) && (!status || reviews.get(p.name).status===status) &&
       (!search || [p.name,p.description,p.provenance.title,p.provenance.author].join(' ').toLowerCase().includes(search));
  }
  function render() {
    visibility.disconnect();plots=[]; $('grid').replaceChildren(); $('compare-grid').replaceChildren();
    let visible=0;
    patterns.forEach((p,i) => { if (matches(p)) { $('grid').append(card(i)); visible++; } });
    for (const i of compared) $('compare-grid').append(card(i,true));
    $('comparison').hidden=compared.size===0;
    $('empty').hidden=visible!==0;
    $('visible').textContent=`${visible} of ${patterns.length} candidates`;
    const counts={keep:0,maybe:0,skip:0,unreviewed:0};
    for (const r of reviews.values()) counts[r.status]++;
    $('counts').textContent=`${counts.keep} kept · ${counts.maybe} maybe · ${counts.skip} skipped`;
    $('export-pack').disabled=$('export-score').disabled=true;
    dirty=true;
  }
  for (const family of [...new Set(patterns.map(p=>p.provenance.family))]) {
    const o=node('option','',family);o.value=family; $('family').append(o);
  }
  const collectionLabels = new Map([
    ['core','Original core'],['initial-01','Initial collection'],
    ['expansion-02','Expansion 02'],['atlas-03','Motion Atlas / 256'],['continuum-04','Continuum / 320'],['club-05','Club Rhythms / 144'],['dancefloor-06','Dancefloor 06 / 944 new']
  ]);
  for (const id of [...new Set(patterns.map(p=>p.provenance.collection_id || 'core'))]) {
    const o=node('option','',collectionLabels.get(id) || id);o.value=id;$('collection').append(o);
  }
  for (const id of ['collection','family','review','search']) $(id).addEventListener('input',render);
  $('clear-compare').onclick=() => { compared.clear();render(); };
  $('clear-review').onclick=() => {
    if (confirm('Clear all Keep / Maybe / Skip choices and notes? Export your review first to save a copy.')) {
      for (const p of patterns) reviews.set(p.name,{status:'unreviewed',note:''}); save();render();
    }
  };

  function selectedPack() {
    throw new Error('Release demos are read-only native snapshots; use repository authoring data.');
    const kept=patterns.filter(p=>reviews.get(p.name).status==='keep');
    if (!kept.length) throw new Error('Mark at least one candidate Keep.');
    return {...data.pack,patterns:kept};
  }
  function selectedScores() {
    throw new Error('Release demos are read-only native snapshots; use repository authoring data.');
    const kept=data.score.patterns.filter(p=>reviews.get(p.name).status==='keep');
    if (!kept.length) throw new Error('Mark at least one candidate Keep.');
    return {...data.score,patterns:kept};
  }
  function download(filename,doc) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  $('export-choices').onclick=() => download('DanceRudiments-'+data.collection_id+'-review.json',reviewDocument());
  $('export-pack').onclick=() => download('DanceRudiments-chosen.compiled.json',selectedPack());
  $('export-score').onclick=() => download('DanceRudiments-chosen.score.json',selectedScores());
  $('import-choices').onchange=async () => {
    const file=$('import-choices').files[0];if (!file) return;
    try {
      if (file.size>1024*1024) throw new Error('Review exceeds 1 MiB.');
      importReview(JSON.parse(await file.text()));
    } catch (error) { message(error.message,true); }
    $('import-choices').value='';
  };

  function sizeCanvas(canvas) {
    const box=canvas.getBoundingClientRect();
    const dpr=Math.min(devicePixelRatio||1,2);
    const w=Math.max(1,Math.round(box.width*dpr)), h=Math.max(1,Math.round(box.height*dpr));
    if (canvas.width!==w || canvas.height!==h) { canvas.width=w;canvas.height=h;return true; }
    return false;
  }
  function sample(i,pip) {
    if (!native) throw new Error('Native sampler not ready');
    if (!Number.isInteger(i) || i<0 || i>=patterns.length || !Number.isInteger(pip) || pip < -2147483648 || pip > 2147483647)
      throw new Error('Invalid native sample index or int32 pip');
    return [0,1,2].map(axis=>native.sample_component(i,pip,axis));
  }
  const curves=[];
  function makeBackground(plot) {
    if (!curves[plot.i]) curves[plot.i]=Array.from(
      {length:patterns[plot.i].period_pips},(_,pip)=>sample(plot.i,pip));
    const {stage,wave,i}=plot, w=stage.width,h=stage.height;
    const dpr=Math.min(devicePixelRatio||1,2), scale=Math.min(w*.38,h*.4)*amplitude;
    const bg=document.createElement('canvas');bg.width=w;bg.height=h;
    const ctx=bg.getContext('2d');ctx.fillStyle='#111923';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#273449';ctx.lineWidth=dpr*.65;ctx.setLineDash([3*dpr,5*dpr]);
    ctx.beginPath();ctx.moveTo(w/2,12*dpr);ctx.lineTo(w/2,h-12*dpr);ctx.moveTo(14*dpr,h/2);ctx.lineTo(w-14*dpr,h/2);ctx.stroke();ctx.setLineDash([]);
    if ($('trails').checked) {
      ctx.strokeStyle='#556c83';ctx.lineWidth=dpr;ctx.beginPath();
      curves[i].forEach((v,j)=>{const q=project(v),x=w/2+q[0]*scale,y=h/2+q[1]*scale;j?ctx.lineTo(x,y):ctx.moveTo(x,y);});
      ctx.closePath();ctx.stroke();
    }
    ctx.fillStyle='#6b8098';ctx.font=`${10*dpr}px system-ui`;ctx.fillText('−X',9*dpr,h/2-7*dpr);ctx.fillText('+X',w-24*dpr,h/2-7*dpr);
    plot.background=bg;plot.scale=scale;plot.amp=amplitude;
    const wb=document.createElement('canvas');wb.width=wave.width;wb.height=wave.height;
    const wc=wb.getContext('2d');wc.fillStyle='#111923';wc.fillRect(0,0,wb.width,wb.height);
    const period=patterns[i].period_pips;
    wc.strokeStyle='#2b374a';wc.lineWidth=dpr*.6;
    for (let p=0;p<=period;p+=64) { const x=p/period*wb.width;wc.beginPath();wc.moveTo(x,0);wc.lineTo(x,wb.height);wc.stroke(); }
    ['#bcacf8','#83e8d0', ...(curves[i].some(v=>v[2]!==0)?['#eab769']:[])].forEach((color,axis) => {
      wc.strokeStyle=color;wc.lineWidth=dpr;wc.beginPath();
      for(let j=0;j<=period;j++) {
        const x=j/period*wb.width,y=wb.height/2-curves[i][j%period][axis]*(wb.height*.38);
        j?wc.lineTo(x,y):wc.moveTo(x,y);
      } wc.stroke();
    });
    if (patterns[i].provenance.event_markers) {
      wc.fillStyle='#eab769';
      for(const m of patterns[i].provenance.event_markers) {
        const v=m.beat.split('/').map(Number),b=v[0]/(v[1]||1);
        wc.fillRect(b/(period/64)*wb.width,wb.height-3*dpr,Math.max(1,dpr),3*dpr);
      }
    }
    plot.waveBackground=wb;
  }
  function draw(beat=beatNow()) {
    if (!native) return;
    const absolutePip=Math.floor(beat*64+1e-8);
    const pip=absolutePip;
    $('clock').textContent=`Beat ${Math.floor(beat)+1} · pip ${((absolutePip%64)+64)%64}`;
    $('seek').value=((pip%phrasePips)+phrasePips)%phrasePips; drawBeatScore(beat);
    renderedLastFrame=0;
    for (const plot of plots) {
      if (!plot.visible) continue;
      renderedLastFrame++;
      const resized=sizeCanvas(plot.stage)|sizeCanvas(plot.wave);
      if (resized || !plot.background || plot.amp!==amplitude) makeBackground(plot);
      const {stage,wave,i}=plot;
      const ctx=stage.getContext('2d');ctx.drawImage(plot.background,0,0);
      const dpr=Math.min(devicePixelRatio||1,2), scale=plot.scale;
      if ($('trails').checked) {
        for(let back=24;back>=4;back-=4) {
          const v=sample(i,pip-back);ctx.globalAlpha=.08+(1-back/28)*.35;ctx.fillStyle='#83e8d0';
          ctx.beginPath();ctx.arc(stage.width/2+project(v)[0]*scale,stage.height/2+project(v)[1]*scale,2.5*dpr,0,Math.PI*2);ctx.fill();
        } ctx.globalAlpha=1;
      }
      const v=sample(i,pip),q=project(v),x=stage.width/2+q[0]*scale,y=stage.height/2+q[1]*scale;
      ctx.fillStyle='#83e8d0';ctx.beginPath();ctx.arc(x,y,6*dpr,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle='#d3fff1';ctx.lineWidth=dpr;ctx.stroke();
      ctx.fillStyle='#9db0c8';ctx.font=`${10*dpr}px ui-monospace,monospace`;
      ctx.fillText(`x ${v[0].toFixed(2)}   y ${v[1].toFixed(2)}   z ${v[2].toFixed(2)}`,10*dpr,stage.height-9*dpr);
      const wc=wave.getContext('2d');wc.drawImage(plot.waveBackground,0,0);
      const local=((pip%patterns[i].period_pips)+patterns[i].period_pips)%patterns[i].period_pips;
      wc.strokeStyle='#edf5ff';wc.lineWidth=dpr;wc.beginPath();
      wc.moveTo(local/patterns[i].period_pips*wave.width,0);wc.lineTo(local/patterns[i].period_pips*wave.width,wave.height);wc.stroke();
    }
    dirty=false;
  }
  function frame() { if (running || dirty) draw(); requestAnimationFrame(frame); }
  // Small documented test/debug surface; never runs user-provided code.
  window.audition={ready:false, sample, metadata:()=>patterns, setBeat:(b)=>{pause();setBeat(b);draw();},
    review:reviewDocument,importReview,setStatus,selectedPack,selectedScores,
    compare:(ids)=>{if(ids.length>4 || ids.some(n=>!names.has(n))) throw new Error('Invalid comparison');
       compared.clear();ids.forEach(n=>compared.add(names.get(n)));if(ids.length && $('follow-beat').checked)followBeat(ids[0]);render();},
    state:()=>({running,beat:beatNow(),storageOK,count:patterns.length,engine:'C++/WebAssembly',midi:transport.state(),selectedBeat:selectedBeat?.id,beatCount:beats.size,renderedLastFrame,plotCount:plots.length}),
    packSha256:data.pack_sha256,
    beatMetadata:()=>[...beats.values()],selectBeat,
    transport, midiExport:()=>DanceBeat.midiWrite(selectedBeat,bpm),
    importMidi:bytes=>importMidi(bytes,'Imported MIDI'),followBeat};
  render();
  (async () => {
    try {
      const bytes=decodeBase64(data.wasm);
      const result=await WebAssembly.instantiate(bytes,{});native=result.instance.exports;
      if (native.pattern_count()!==patterns.length || patterns.some((p,i)=>native.pattern_period(i)!==p.period_pips))
        throw new Error('Native bank does not match the embedded collection');
      window.audition.ready=true; $('engine').textContent='C++ / WASM · offline'; $('play').disabled=false;
      if (!storageOK) message('Browser storage is unavailable; export your review to save it.',true);
      else if (reducedMotion.matches) message('Reduced motion: starting paused. Use pip stepping or choose Play explicitly.');
      dirty=true;requestAnimationFrame(frame);
    } catch(error) {
      $('engine').textContent='Native sampler unavailable';
      message('Preview could not start: '+error.message+'. No JavaScript movement fallback is used.',true);
    }
  })();
})();
