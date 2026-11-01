/** Local authoring UI. The server owns inference, correction and saved decisions.
 * This module only maps the audio clock to the existing native recording player.
 */
import '../song_loop_viewer/alignment-review.js';

const timing = globalThis.DanceRudimentsTimingReview;
const HASH = /^[a-f0-9]{64}$/;
const TOKEN = /^[A-Za-z0-9_-]{32,128}$/;
const finite = n => typeof n === 'number' && Number.isFinite(n);
const clone = value => JSON.parse(JSON.stringify(value));
const requireValue = (ok, message) => { if (!ok) throw Error(message); };
const MAX_DOCUMENT_BYTES = 8 * 1024 * 1024;
export const MAX_LOOP_BEATS = 32;

export function workspaceToken(location) {
  const value = new URLSearchParams(location.hash.replace(/^#/, '')).get('review');
  if (value === null) return null;
  requireValue(location.protocol === 'http:' && ['127.0.0.1','localhost','[::1]','::1'].includes(location.hostname),
    'A motion review workspace must run on the local loopback server.');
  requireValue(TOKEN.test(value), 'The local review link is invalid.');
  return value;
}

function fileDescriptor(file, label, limit) {
  requireValue(file && typeof file.url === 'string' && /^\/api\/files\/[A-Za-z0-9_-]+$/.test(file.url) &&
    HASH.test(file.sha256) && Number.isSafeInteger(file.byte_length) && file.byte_length > 0 && file.byte_length <= limit,
    `${label} is missing a bounded local file identity.`);
}

export function validateWorkspaceSession(value, config) {
  requireValue(value?.format === 'dancerudiments.loop-review-workspace.v1' && value.schema_version === 1 &&
    Number.isSafeInteger(value.revision) && value.revision >= 1, 'Unknown local review session.');
  const scene = config.scenes.find(s => s.id === value.scene_id), selected = value.selection;
  requireValue(scene && selected?.format === 'dancerudiments.loop-selection.v1' && selected.schema_version === 1 &&
    HASH.test(selected.selection_id), 'The review selection is missing.');
  requireValue(selected.source?.original_source_sha256 === scene.sourceSha256 &&
    selected.source?.profile_sha256 === scene.expectedProfile.fingerprint &&
    HASH.test(selected.source?.capture_file_sha256) && HASH.test(selected.source?.capture_sha256),
    'The review belongs to a different source Action or rig.');
  const bounds = selected.bounds;
  requireValue(finite(bounds?.start_seconds) && finite(bounds?.end_seconds) && bounds.end_seconds > bounds.start_seconds &&
    Number.isSafeInteger(selected.beat_count) && selected.beat_count >= 1 && selected.beat_count <= MAX_LOOP_BEATS &&
    selected.sample_count === selected.beat_count * 64, 'Invalid selected loop bounds or beat count.');
  requireValue(config.reviewTarget && ['id','asset_sha256','rig_sha256','calibration_sha256'].every(key =>
    value.target?.[key] === config.reviewTarget[key]), 'The saved target or calibration differs from this Kandi view.');
  requireValue(value.target.asset_sha256 === config.character.fbxAssetSha256 &&
    value.target.rig_sha256 === config.character.assets.rig.sha256,
    'Kandi target assets differ from the review.');
  fileDescriptor(value.files?.motion, 'Finished motion', 64 * 1024 * 1024);
  fileDescriptor(value.files?.repair, 'Repair report', 2 * 1024 * 1024);
  fileDescriptor(value.files?.audio, 'Audio master', 256 * 1024 * 1024);
  requireValue(value.files.motion.sha256 === selected.files?.motion?.sha256 &&
    value.files.repair.sha256 === selected.files?.repair?.sha256, 'Finished files differ from the selected derivative.');
  const entry = value.alignment;
  requireValue(entry?.report?.format === 'stemlab.motion-alignment.v1' && HASH.test(entry.report_sha256) &&
    HASH.test(entry.report_content_sha256) &&
    entry.report.motion_source?.sha256 === selected.source.capture_file_sha256 &&
    entry.report.audio_source?.sha256 === value.files.audio.sha256,
    'Timing evidence belongs to different original source bytes.');
  if (value.timing_revision) {
    timing.validateSavedRevision(entry, value.timing_revision);
    requireValue(HASH.test(value.timing_revision_content_sha256), 'Saved timing revision identity is missing.');
  }
  requireValue(['human','automated_test'].includes(value.review_kind ?? 'human'), 'Unknown reviewer kind.');
  return value;
}

export function forwardTime(segments, seconds) {
  if (!finite(seconds)) return null;
  for (const segment of segments) {
    if (seconds < segment.motion_seconds_range[0] || seconds > segment.motion_seconds_range[1]) continue;
    for (let i = 1; i < segment.anchors.length; i++) {
      const a = segment.anchors[i-1], b = segment.anchors[i];
      if (seconds <= b.motion_seconds) return a.audio_seconds +
        (seconds-a.motion_seconds)/(b.motion_seconds-a.motion_seconds)*(b.audio_seconds-a.audio_seconds);
    }
  }
  return null;
}

export function loopPlayback(selection, segments) {
  const [start,end] = [selection.bounds.start_seconds,selection.bounds.end_seconds];
  // A loop cannot traverse a gap, even if the endpoints happen to map.
  const segment = segments.find(s => s.motion_seconds_range[0] <= start && end <= s.motion_seconds_range[1]);
  requireValue(segment, 'The timing mapping must cover the whole selected loop without a gap.');
  const first = forwardTime([segment],start), last = forwardTime([segment],end);
  requireValue(finite(first) && finite(last) && last > first, 'The selected loop has no valid audio interval.');
  return {source_seconds_range:[start,end],audio_seconds_range:[first,last],
    period_pips:selection.sample_count,mapping_segments:[clone(segment)]};
}

export function audioSecondsToPip(playback, seconds, {repeat=false}={}) {
  requireValue(finite(seconds), 'Audio time must be finite.');
  const [a,b] = playback.audio_seconds_range;
  if (seconds < a) return null;
  if (repeat && seconds >= b) seconds = a + (seconds-a) % (b-a);
  if (seconds >= b) return null;
  const source = timing.inverseTime(playback.mapping_segments,seconds);
  const [start,end] = playback.source_seconds_range;
  if (source === null || source < start || source >= end) return null;
  return Math.min(playback.period_pips-1,Math.floor((source-start)/(end-start)*playback.period_pips));
}

export function parseManualAnchors(text) {
  if (typeof text !== 'string' || !text.trim()) return null;
  const lines = text.trim().split(/\r?\n/);
  requireValue(lines.length >= 2 && lines.length <= 2000, 'Use at least two source → audio anchor pairs.');
  return lines.map(line => {
    const pair = line.trim().split(/[\s,]+/).map(Number);
    requireValue(pair.length === 2 && pair.every(finite), 'Each anchor line needs source seconds and audio seconds.');
    return {motion_seconds:pair[0],audio_seconds:pair[1]};
  });
}

async function sha256(bytes) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
}

export function createWorkspaceClient(token, {fetch: request=globalThis.fetch,signal}={}) {
  requireValue(TOKEN.test(token), 'Invalid local workspace capability.');
  async function bytes(path, limit, init={}) {
    requireValue(/^\/api\/(session|finish|review|draft|export|files\/[A-Za-z0-9_-]+)$/.test(path), 'Invalid local workspace route.');
    const response = await request(path,{...init,signal,cache:'no-store',credentials:'same-origin',redirect:'error',
      headers:{...init.headers,'X-Loop-Review-Token':token}});
    const declared=Number(response.headers.get('content-length'));
    requireValue(!Number.isFinite(declared)||declared<=limit,'Workspace response exceeds its size limit.');
    const reader=response.body?.getReader(); requireValue(reader,'Streaming workspace reads are unavailable.');
    const chunks=[]; let count=0;
    try {
      while(true){const item=await reader.read();if(item.done)break;
        count+=item.value.length;requireValue(count<=limit,'Workspace response exceeds its size limit.');chunks.push(item.value);}
    } catch(error) { await reader.cancel().catch(()=>{});throw error; }
    finally { reader.releaseLock(); }
    const data=new Uint8Array(count);let at=0;for(const item of chunks){data.set(item,at);at+=item.length;}
    if(!response.ok){
      let message=`Workspace request failed (${response.status}).`;
      try{message=JSON.parse(new TextDecoder().decode(data)).error||message;}catch{}
      const error=Error(message);error.status=response.status;throw error;
    }
    return data;
  }
  return {
    async json(path, payload) {
      const data=await bytes(path,MAX_DOCUMENT_BYTES,payload===undefined?{}:{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(data));
    },
    async file(descriptor, limit) {
      fileDescriptor(descriptor,'Workspace asset',limit);
      const data=await bytes(descriptor.url,limit);
      requireValue(data.length===descriptor.byte_length&&await sha256(data)===descriptor.sha256,
        'Workspace file bytes do not match their saved identity.');
      return data;
    },
  };
}

function createElement(tag,text,className) {
  const element=document.createElement(tag);if(text!==undefined)element.textContent=text;
  if(className)element.className=className;return element;
}

export function createLoopWorkspace({sidebar,host,config,location=globalThis.location}) {
  let token;
  try { token=workspaceToken(location); }
  catch(error){sidebar.append(createElement('p',error.message,'rhythm-error'));return null;}
  if(token===null)return null;
  const controller=new AbortController(),client=createWorkspaceClient(token,{signal:controller.signal});
  const section=createElement('section',undefined,'loop-workspace');section.setAttribute('aria-label','Local loop authoring workspace');
  section.append(createElement('h2','Finish a loop'),createElement('p','Choose a phrase, audition it with the master, and save your timing and Kandi review.','loop-intro'));
  const scope=createElement('p','Automated test workspace · no human approval','loop-scope');scope.hidden=true;section.append(scope);
  const status=createElement('p','Opening your local review session…','loop-status');status.setAttribute('role','status');section.append(status);
  const error=createElement('p','','rhythm-error');error.setAttribute('role','alert');error.hidden=true;section.append(error);
  const controls={};
  function field(id,label,type='text',parent=section){
    const wrap=createElement('label',label,'loop-field'),input=createElement(type==='textarea'?'textarea':'input');
    if(type!=='textarea')input.type=type;
    input.id=`loop-${id}`;input.setAttribute('aria-label',label);wrap.append(input);parent.append(wrap);controls[id]=input;return input;
  }
  function select(id,label,options,parent=section){
    const wrap=createElement('label',label,'loop-field'),input=createElement('select');input.id=`loop-${id}`;
    input.setAttribute('aria-label',label);for(const [value,text] of options){const option=createElement('option',text);option.value=value;input.append(option);}
    wrap.append(input);parent.append(wrap);controls[id]=input;return input;
  }
  function button(id,label,handler,parent=section){
    const input=createElement('button',label,'button');input.id=`loop-${id}`;input.type='button';
    input.addEventListener('click',()=>run(handler));parent.append(input);controls[id]=input;return input;
  }
  let state=null,busy=false,loaded=false,dirty=false,boundaryDirty=false,closed=false,serial=0;
  let audioUrl=null,audioHash=null,motionHash=null,preservedSegments=null,currentPlayback=null,repeatCount=0;
  const audio=createElement('audio');audio.id='loop-audio';audio.controls=true;audio.preload='metadata';
  audio.setAttribute('aria-label','Exact source master for loop review');section.append(audio);
  const audioActions=createElement('div',undefined,'loop-buttons');section.append(audioActions);
  button('load','Load Kandi + audio',async()=>{requireValue(state,'Session is not ready.');await loadAssets();},audioActions);
  button('audition','Audition selected loop',async()=>{requireValue(loaded,'Load Kandi and audio first.');
    currentPlayback=getPlayback();host.pause();audio.currentTime=currentPlayback.audio_seconds_range[0];await audio.play();},audioActions);
  button('original','Compare original',()=>{requireValue(loaded,'Load Kandi first.');host.mode('original');},audioActions);
  button('finished','Finished clip',()=>{requireValue(loaded,'Load Kandi first.');host.mode('finished');},audioActions);
  const repeat=field('repeat','Repeat the selected audio and motion','checkbox');
  const bounds=createElement('div',undefined,'loop-grid');section.append(bounds);
  const start=field('start','Loop in · source seconds','number',bounds),end=field('end','Loop out · source seconds','number',bounds);
  start.step=end.step='any';
  const beats=field('beats','Beats in this phrase','number');beats.min='1';beats.max=String(MAX_LOOP_BEATS);beats.step='1';
  const beatActions=createElement('div',undefined,'loop-buttons');section.append(beatActions);
  button('half-beats','Half as many beats',()=>{const n=Number(beats.value);requireValue(n%2===0&&n>=2,'The phrase needs an even beat count.');beats.value=String(n/2);changed(true);},beatActions);
  button('double-beats','Twice as many beats',()=>{const n=Number(beats.value);requireValue(n>=1&&n<=MAX_LOOP_BEATS/2,`The phrase is limited to ${MAX_LOOP_BEATS} beats.`);beats.value=String(n*2);changed(true);},beatActions);
  section.append(createElement('p','Beat count changes the musical interpretation. Audio playback speed stays unchanged.','loop-hint'));
  button('finish','Finish these boundaries',async()=>{
    audio.pause();const result=await client.json('/api/finish',{expected_revision:state.revision,
      start_seconds:Number(start.value),end_seconds:Number(end.value),beats:Number(beats.value)});
    await apply(result);if(loaded)await loadAssets();status.textContent='The updated phrase passed correction and native checks. Review its timing, feet and repeat boundary.';
  });
  const candidates=select('candidate','Timing hypothesis',[]),offset=field('offset','Phase correction · audio seconds','number');offset.step='.001';offset.min='-30';offset.max='30';
  const detail=createElement('details');detail.append(createElement('summary','Manual timing anchors'));section.append(detail);
  const anchors=field('anchors','Source → audio anchors · seconds','textarea',detail);anchors.rows=4;anchors.placeholder='1.2, 14.6\n2.4, 16.9';
  detail.append(createElement('p','One source time and audio time per line. Use increasing pairs inside known coverage. Leave blank to use the selected hypothesis.','loop-hint'));
  const beatOne=field('beat-one','Beat one · audio seconds (optional)','number');beatOne.step='any';
  const meter=field('meter','Meter (optional)');meter.placeholder='4/4';
  const reviewer=field('reviewer','Reviewer');reviewer.maxLength=160;
  select('seam','Repeat seam',[['unreviewed','Not reviewed'],['accept','Accept'],['reject','Reject']]);
  select('feet','Foot placement',[['unreviewed','Not reviewed'],['accept','Accept'],['reject','Reject']]);
  select('skin','Skin and intersections',[['unreviewed','Not reviewed'],['accept','Accept'],['reject','Reject']]);
  const notes=field('notes','Review notes','textarea');notes.maxLength=4000;notes.rows=3;
  const saveActions=createElement('div',undefined,'loop-buttons');section.append(saveActions);
  button('draft','Save draft',async()=>{const result=await client.json('/api/draft',{expected_revision:state.revision,draft:getDraft()});
    await apply(result);status.textContent='Draft saved. Your current work will reopen with this session.';},saveActions);
  button('save','Save timing + visual review',async()=>{
    requireValue(loaded&&audioHash===state.files.audio.sha256&&motionHash===state.files.motion.sha256,'Load the exact current audio and finished motion before reviewing.');
    requireValue(!boundaryDirty,'Finish the updated boundaries before saving a review.');
    const draft=getDraft();getPlayback();
    const revision=timing.makeRevision(state.alignment,Number(candidates.value),{offset:draft.offset_seconds,
      reviewer:draft.reviewer,beatOne:draft.beat_one_audio_seconds,meter:draft.meter,manualAnchors:draft.manual_anchors,
      previousRevision:state.timing_revision??null,previousRevisionSha256:state.timing_revision_content_sha256??null});
    if(preservedSegments)revision.mapping_segments=clone(preservedSegments);
    const result=await client.json('/api/review',{expected_revision:state.revision,timing_revision:revision,
      reviewer:draft.reviewer,verdicts:draft.verdicts,review_kind:state.review_kind??'human',notes:draft.notes,draft});
    await apply(result);status.textContent=state.export_ready?
      (state.review_kind==='automated_test'?'Test decisions saved. The automated fixture is ready to export.':'Your timing and visual decisions are saved. The reviewed loop is ready to export.'):
      'Review saved. Export remains unavailable until all required decisions are accepted.';
  },saveActions);
  button('reload','Reload saved session',async()=>{audio.pause();const result=await client.json('/api/session');await apply(result);
    if(loaded)await loadAssets();status.textContent='Saved selection and review restored.';},saveActions);
  const exportDetails=createElement('details');exportDetails.append(createElement('summary','Export optional motion package'));section.append(exportDetails);
  field('package-id','Package ID','text',exportDetails).value='reviewed_loop';
  field('version','Package version','text',exportDetails).value='1.0.0';
  field('title','Package title','text',exportDetails).value='Reviewed motion loop';
  button('export','Download reviewed loop',async()=>{
    requireValue(state.export_ready&&!dirty&&!boundaryDirty,'Save a complete current review before exporting.');
    const result=await client.json('/api/export',{expected_revision:state.revision,package_id:controls['package-id'].value,
      version:controls.version.value,title:controls.title.value});
    const bytes=await client.file(result,64*1024*1024),url=URL.createObjectURL(new Blob([bytes],{type:'application/zip'}));
    const link=createElement('a');link.href=url;link.download=result.filename||'reviewed-loop.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    await apply(await client.json('/api/session'));
    status.textContent='The reviewed native motion package was downloaded with its timing, visual decisions and provenance.';
  },exportDetails);
  section.append(createElement('p','Your local server saves review documents separately from the original motion. Audio and Kandi assets stay outside the exported package.','loop-hint'));
  sidebar.prepend(section);

  function getDraft(){
    const match=meter.value.trim().match(/^(\d+)\s*\/\s*(\d+)$/);
    requireValue(!meter.value.trim()||match,'Use a meter such as 4/4, or leave it blank.');
    return {start_seconds:Number(start.value),end_seconds:Number(end.value),beats:Number(beats.value),
      candidate_id:state.alignment.report.candidates[Number(candidates.value)]?.candidate_id??null,
      offset_seconds:Number(offset.value),manual_anchors:parseManualAnchors(anchors.value),reviewer:reviewer.value.trim(),
      beat_one_audio_seconds:beatOne.value.trim()===''?null:Number(beatOne.value),meter:match?[Number(match[1]),Number(match[2])]:null,
      verdicts:{seam:controls.seam.value,feet:controls.feet.value,skin:controls.skin.value},notes:notes.value};
  }
  function segments(){
    if(preservedSegments)return clone(preservedSegments);
    return timing.shiftedSegments(state.alignment,Number(candidates.value),Number(offset.value),parseManualAnchors(anchors.value));
  }
  function getPlayback(){requireValue(!boundaryDirty,'Finish the updated boundaries before auditioning.');return loopPlayback(state.selection,segments());}
  function changed(boundaries=false,clearMapping=true){
    audio.pause();dirty=true;boundaryDirty=boundaryDirty||boundaries;
    if(clearMapping)preservedSegments=null;currentPlayback=null;
    for(const name of ['seam','feet','skin'])controls[name].value='unreviewed';
    status.textContent=boundaries?'Boundaries changed. Finish them to generate and verify the new loop.':'Timing changed. Audition the updated result, then review it again.';draw();
  }
  for(const item of [start,end,beats])item.addEventListener('input',()=>changed(true));
  for(const item of [candidates,offset,anchors])item.addEventListener('input',()=>changed(false));
  for(const item of [beatOne,meter])item.addEventListener('input',()=>changed(false,false));
  for(const item of [reviewer,controls.seam,controls.feet,controls.skin,notes])item.addEventListener('input',()=>{dirty=true;draw();});
  audio.addEventListener('play',()=>{try{requireValue(loaded,'Load the verified motion first.');currentPlayback=getPlayback();host.pause();}catch(e){audio.pause();error.textContent=e.message;error.hidden=false;}});
  audio.addEventListener('seeked',()=>{if(loaded){try{currentPlayback=getPlayback();}catch{currentPlayback=null;}}});
  audio.addEventListener('error',()=>{error.textContent='The exact local master could not be decoded by this browser.';error.hidden=false;});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)audio.pause();},{signal:controller.signal});

  async function run(action){
    if(busy||closed)return;busy=true;error.hidden=true;audio.pause();draw();
    try{await action();}catch(cause){error.textContent=cause?.message??String(cause);error.hidden=false;
      if(cause?.status===409)status.textContent='This session changed elsewhere. Reload the saved session before continuing.';
    }finally{busy=false;draw();}
  }
  function draw(){
    for(const element of section.querySelectorAll('input,select,textarea,button'))element.disabled=busy||!state;
    for(const id of ['audition','original','finished','save'])controls[id].disabled=busy||!loaded||!state;
    controls.save.disabled=controls.save.disabled||boundaryDirty;
    controls.export.disabled=busy||!state?.export_ready||dirty||boundaryDirty;
    audio.hidden=!audioUrl;
  }
  async function apply(value){
    validateWorkspaceSession(value,config);state=value;dirty=false;boundaryDirty=false;currentPlayback=null;preservedSegments=null;
    scope.hidden=state.review_kind!=='automated_test';
    const selected=state.selection,draft=state.draft??{},saved=state.timing_revision;
    start.value=String(draft.start_seconds??selected.bounds.start_seconds);end.value=String(draft.end_seconds??selected.bounds.end_seconds);
    beats.value=String(draft.beats??selected.beat_count);
    boundaryDirty=Number(start.value)!==selected.bounds.start_seconds||Number(end.value)!==selected.bounds.end_seconds||Number(beats.value)!==selected.beat_count;
    candidates.replaceChildren();state.alignment.report.candidates.forEach((candidate,index)=>{
      const score=finite(candidate.score_uncalibrated)?` · ${(candidate.score_uncalibrated*100).toFixed(1)}% event agreement`:'';
      const option=createElement('option',`${index+1}. ${candidate.method.replaceAll('_',' ')}${score}`);option.value=String(index);candidates.append(option);
    });
    const id=draft.candidate_id??saved?.candidate_id;
    const chosen=state.alignment.report.candidates.findIndex(c=>c.candidate_id===id);candidates.value=String(Math.max(0,chosen));
    offset.value=String(draft.offset_seconds??0);
    anchors.value=(draft.manual_anchors??[]).map(a=>`${a.motion_seconds}, ${a.audio_seconds}`).join('\n');
    if(saved&&(state.review||!Object.keys(draft).length))preservedSegments=clone(saved.mapping_segments);
    beatOne.value=draft.beat_one_audio_seconds??saved?.beat_one_audio_seconds??'';
    const savedMeter=draft.meter??saved?.meter;meter.value=savedMeter?savedMeter.join('/'):'';
    reviewer.value=draft.reviewer??state.review?.reviewer??saved?.reviewer??'';
    notes.value=draft.notes??state.review?.notes??'';
    for(const name of ['seam','feet','skin'])controls[name].value=draft.verdicts?.[name]??state.review?.verdicts?.[name]??'unreviewed';
    if(loaded&&(motionHash!==state.files.motion.sha256||audioHash!==state.files.audio.sha256))audio.pause();
    status.textContent=state.review_kind==='automated_test'?'Automated test workspace · no human approval.':
      state.review?'Saved review loaded. Audition the phrase or continue editing.':'Choose a phrase and timing hypothesis. No musical or visual decisions have been accepted.';
    draw();
  }
  async function loadAssets(){
    const snapshot=state;audio.pause();await host.prepare(snapshot);const number=++serial;
    const motionNeeded=motionHash!==snapshot.files.motion.sha256||!loaded;
    if(motionNeeded){const [motion,repair]=await Promise.all([
      client.file(snapshot.files.motion,64*1024*1024),client.file(snapshot.files.repair,2*1024*1024)]);
      if(closed||number!==serial)return;
      const finished=await host.loadFinished(motion,JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(repair)));
      if(closed||number!==serial)return;
      requireValue(finished,'The matching source scene was unloaded before the finished motion was ready.');
      motionHash=snapshot.files.motion.sha256;
    }
    if(audioHash!==snapshot.files.audio.sha256){
      const bytes=await client.file(snapshot.files.audio,256*1024*1024);if(closed||number!==serial)return;
      if(audioUrl)URL.revokeObjectURL(audioUrl);
      audioUrl=URL.createObjectURL(new Blob([bytes],{type:snapshot.files.audio.mime_type||'audio/mpeg'}));
      audio.src=audioUrl;audioHash=snapshot.files.audio.sha256;audio.load();
    }
    if(audio.readyState<1)await new Promise((resolve,reject)=>{
      let timer;
      const finish=error=>{clearTimeout(timer);audio.removeEventListener('loadedmetadata',ready);
        audio.removeEventListener('error',failed);controller.signal.removeEventListener('abort',aborted);
        error?reject(error):resolve();};
      const ready=()=>finish(),failed=()=>finish(Error('The exact local master could not be decoded by this browser.')),
        aborted=()=>finish(Error('The review workspace was closed.'));
      audio.addEventListener('loadedmetadata',ready,{once:true});audio.addEventListener('error',failed,{once:true});
      controller.signal.addEventListener('abort',aborted,{once:true});
      timer=setTimeout(()=>finish(Error('The exact local master did not become ready for playback.')),15000);
      if(audio.error)failed();else if(controller.signal.aborted)aborted();else if(audio.readyState>=1)ready();
    });
    if(closed||number!==serial)return;loaded=true;host.mode('finished');
    currentPlayback=getPlayback();audio.currentTime=currentPlayback.audio_seconds_range[0];
    host.pause();status.textContent='Exact master and native motion loaded. Play the selected phrase, then record your own decisions.';draw();
  }
  function frame(){
    if(!loaded||closed||!state)return false;
    let mapped=null;
    try{
      currentPlayback??=getPlayback();const [first,last]=currentPlayback.audio_seconds_range;
      if(audio.currentTime>=last){
        if(repeat.checked&&!audio.paused){const overflow=(audio.currentTime-first)%(last-first);audio.currentTime=first+overflow;repeatCount++;}
        else if(!audio.paused)audio.pause();
      }
      const pip=audioSecondsToPip(currentPlayback,audio.currentTime);
      if(pip!==null){const source=timing.inverseTime(currentPlayback.mapping_segments,audio.currentTime);
        mapped={pip,source_seconds:source,selection:state.selection};}
    }catch{}
    host.audioPose(mapped);return true;
  }
  function detached(){serial++;audio.pause();loaded=false;motionHash=null;currentPlayback=null;draw();}
  function dispose(){closed=true;serial++;controller.abort();audio.pause();audio.removeAttribute('src');audio.load();
    if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=null;loaded=false;}
  run(async()=>apply(await client.json('/api/session')));
  return {frame,detached,dispose,pause:()=>audio.pause(),active:()=>loaded,
    diagnostics:()=>({enabled:true,revision:state?.revision??null,selectionId:state?.selection?.selection_id??null,
      loaded,busy,dirty,boundaryDirty,audioBytesVerified:loaded&&audioHash===state?.files.audio?.sha256,
      motionBytesVerified:loaded&&motionHash===state?.files.motion?.sha256,audioSeconds:audio.currentTime,
      audioPlaying:!audio.paused,repeat:repeat.checked,repeatCount,exportReady:!!state?.export_ready&&!dirty&&!boundaryDirty,
      savedReview:!!state?.review,reviewKind:state?.review_kind??'human',error:error.hidden?null:error.textContent})};
}
