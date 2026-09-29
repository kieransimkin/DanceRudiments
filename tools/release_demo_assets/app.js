'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('data').textContent);
  const patterns = data.pack.patterns;
  const phrasePips = Math.max(...patterns.map(p => p.period_pips));
  $('seek').max = phrasePips - 1;
  const project = v => [v[0]+.25*v[2], v[1]-.2*v[2]];
  const STORAGE = 'dancerudiments-review:' + data.collection_id + ':' + data.pack_sha256;
  const names = new Map(patterns.map((p, i) => [p.name, i]));
  const reviews = new Map(patterns.map(p => [p.name, {status: 'keep', note: ''}]));
  const compared = new Set();
  let native, plots = [], baseBeat = 0, origin = performance.now(), running = false;
  let bpm = 120, amplitude = .7, dirty = true, audioURL = null, storageOK = true;
  const audio = $('audio');
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
    return baseBeat + (running ? (performance.now()-origin)*bpm/60000 : 0);
  }
  function setBeat(value) {
    if (!Number.isFinite(value)) throw new Error('Beat must be finite');
    if (audioURL) {
      const time = Number($('offset').value || 0) + value*60/bpm;
      if (Number.isFinite(audio.duration)) audio.currentTime=Math.max(0,Math.min(audio.duration,time));
    } else { baseBeat=value; origin=performance.now(); }
    dirty=true;
  }
  function updatePlay() { $('play').textContent=running ? 'Pause' : 'Play'; }
  function pause() {
    baseBeat=beatNow(); running=false; audio.pause(); updatePlay(); dirty=true;
  }
  async function play() {
    if (!native) return;
    if (audioURL) {
      try { await audio.play(); }
      catch (error) { message('Audio could not play: '+error.message,true); return; }
    } else { origin=performance.now(); running=true; updatePlay(); }
    dirty=true;
  }
  $('play').onclick=() => running ? pause() : play();
  $('reset').onclick=() => { setBeat(0); dirty=true; };
  $('back').onclick=() => { pause(); setBeat((Math.floor(beatNow()*64+1e-8)-1)/64); };
  $('forward').onclick=() => { pause(); setBeat((Math.floor(beatNow()*64+1e-8)+1)/64); };
  $('bpm').onchange=() => {
    const next=Number($('bpm').value);
    if (!Number.isFinite(next) || next<30 || next>240) { $('bpm').value=bpm; return; }
    baseBeat=beatNow(); origin=performance.now(); bpm=next; dirty=true;
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
    audioURL=URL.createObjectURL(file); audio.src=audioURL;
    message('Local audio loaded. Set its BPM and beat-zero offset, then press Play.');
  };
  $('clear-audio').onclick=() => {
    const current=beatNow(); pause();
    if (audioURL) URL.revokeObjectURL(audioURL);
    audioURL=null; audio.removeAttribute('src'); audio.load(); $('audio-file').value='';
    baseBeat=current; origin=performance.now(); dirty=true; message('Audio removed. Using the internal musical clock.');
  };
  reducedMotion.addEventListener('change', e => { if (e.matches) { pause(); message('Reduced motion enabled. Playback paused; manual stepping remains available.'); } });
  document.addEventListener('visibilitychange',() => { if (document.hidden && !audioURL) pause(); });
  window.addEventListener('resize',() => { dirty=true; });

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
    wave.setAttribute('aria-label','X and Y position curves over one cycle');
    c.append(stage,wave); plots.push({i,stage,wave,background:null,amp:-1});
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
      check.checked ? compared.add(i) : compared.delete(i); render();
    };
    compareLabel.append(check,document.createTextNode('Compare'));
    const source=node('button','source-button',meta.license+' · Details');
    source.onclick=() => showDetail(meta.title,JSON.stringify({name:p.name,source_sha256:p.source_sha256,
                       provenance:meta,diagnostics:p.diagnostics},null,2));
    bottom.append(compareLabel,source); body.append(bottom);
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
    return (!family || p.provenance.family===family) && (!status || reviews.get(p.name).status===status) &&
       (!search || [p.name,p.description,p.provenance.title,p.provenance.author].join(' ').toLowerCase().includes(search));
  }
  function render() {
    plots=[]; $('grid').replaceChildren(); $('compare-grid').replaceChildren();
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
  for (const id of ['family','review','search']) $(id).addEventListener('input',render);
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
  $('export-choices').onclick=() => download('DanceRudiments-initial-review.json',reviewDocument());
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
    $('seek').value=((pip%phrasePips)+phrasePips)%phrasePips;
    for (const plot of plots) {
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
  window.audition={ready:false, sample, setBeat:(b)=>{pause();setBeat(b);draw();},
    review:reviewDocument,importReview,setStatus,selectedPack,selectedScores,
    compare:(ids)=>{if(ids.length>4 || ids.some(n=>!names.has(n))) throw new Error('Invalid comparison');
       compared.clear();ids.forEach(n=>compared.add(names.get(n)));render();},
    state:()=>({running,beat:beatNow(),storageOK,count:patterns.length,engine:'C++/WebAssembly'}),
    packSha256:data.pack_sha256};
  render();
  (async () => {
    try {
      const bytes=Uint8Array.from(atob(data.wasm),c=>c.charCodeAt(0));
      const result=await WebAssembly.instantiate(bytes,{});native=result.instance.exports;
      if (native.pattern_count()!==patterns.length || patterns.some((p,i)=>native.pattern_period(i)!==p.period_pips))
        throw new Error('Native bank does not match the embedded collection');
      patterns.forEach((p,i)=>curves.push(Array.from({length:p.period_pips},(_,pip)=>sample(i,pip))));
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
