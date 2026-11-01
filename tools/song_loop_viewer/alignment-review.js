/* Source-clock timing review for the static preview. Inference stays in StemLab. */
(() => {
  'use strict';
  const HASH=/^[a-f0-9]{64}$/;
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const require=(ok,message)=>{if(!ok)throw Error(message)};
  const clone=x=>JSON.parse(JSON.stringify(x));
  function matchingReviews(reviews,song,motion){
    return reviews.filter(x=>x.report?.audio_source?.sha256===song?.source_sha256&&
      x.report?.motion_source?.sha256===motion?.source_capture_sha256);
  }
  function shiftedSegments(entry,candidateIndex,offset=0){
    require(finite(offset)&&Math.abs(offset)<=30,'Phase correction must be within ±30 seconds.');
    const report=entry.report,candidate=report.candidates?.[candidateIndex];
    require(report.format==='stemlab.motion-alignment.v1'&&candidate,'Choose a valid timing candidate.');
    const segments=clone(candidate.mapping_segments);
    require(Array.isArray(segments)&&segments.length>0&&segments.length<=256,'Missing bounded mapping.');
    let lastMotion=-Infinity,lastAudio=-Infinity;
    for(const segment of segments){
      require(Array.isArray(segment.anchors)&&segment.anchors.length>=2&&segment.anchors.length<=6000,'Invalid timing anchors.');
      for(const anchor of segment.anchors){
        require(finite(anchor.motion_seconds)&&finite(anchor.audio_seconds),'Nonfinite timing anchor.');
        anchor.audio_seconds+=offset;
        require(anchor.motion_seconds>lastMotion&&anchor.audio_seconds>lastAudio,'Timing anchors must increase in both clocks.');
        lastMotion=anchor.motion_seconds;lastAudio=anchor.audio_seconds;
      }
      const first=segment.anchors[0],last=segment.anchors.at(-1);
      segment.motion_seconds_range=[first.motion_seconds,last.motion_seconds];
      segment.audio_seconds_range=[first.audio_seconds,last.audio_seconds];
      for(const kind of ['motion','audio']){
        const [a,b]=segment[`${kind}_seconds_range`];
        require(report[`${kind}_source`].valid_segments_seconds.some(([lo,hi])=>lo<=a&&b<=hi),
          'Phase correction crosses a source boundary or a coverage gap.');
      }
      if(offset!==0)segment.anchor_kind='user_phase_correction';
    }
    return segments;
  }
  function inverseTime(segments,audioSeconds){
    require(finite(audioSeconds),'Audio time must be finite.');
    for(const segment of segments){
      if(audioSeconds<segment.audio_seconds_range[0]||audioSeconds>segment.audio_seconds_range[1])continue;
      const points=segment.anchors;
      for(let i=1;i<points.length;i++)if(audioSeconds<=points[i].audio_seconds){
        const a=points[i-1],b=points[i],weight=(audioSeconds-a.audio_seconds)/(b.audio_seconds-a.audio_seconds);
        return a.motion_seconds+weight*(b.motion_seconds-a.motion_seconds);
      }
    }
    return null; // No extrapolation or interpolation across unknown footage.
  }
  function phaseForSource(motion,seconds){
    if(seconds===null)return null;
    const start=motion.source_clock_start_seconds??motion.source_start_seconds;
    const duration=motion.raw_sample_count/64*60/motion.estimated_bpm;
    const end=motion.loopable?start+duration:start+duration*(motion.raw_sample_count-1)/motion.raw_sample_count;
    if(!finite(seconds)||!finite(start)||!(duration>0)||seconds<start||
       (motion.loopable?seconds>=end:seconds>end))return null;
    return (seconds-start)/duration;
  }
  function makeRevision(entry,candidateIndex,{offset=0,reviewer,beatOne=null,meter=null}={}){
    require(HASH.test(entry.report_sha256)&&HASH.test(entry.report_content_sha256),'Report identity is missing.');
    require(typeof reviewer==='string'&&reviewer.trim().length>0&&reviewer.length<=160,'Enter your reviewer name.');
    const report=entry.report,segments=shiftedSegments(entry,candidateIndex,offset);
    if(beatOne!==null)require(finite(beatOne)&&report.audio_source.valid_segments_seconds.some(([a,b])=>a<=beatOne&&beatOne<=b),
      'Beat one must lie within the audio source.');
    if(meter!==null)require(Array.isArray(meter)&&meter.length===2&&Number.isInteger(meter[0])&&
      meter[0]>=1&&meter[0]<=32&&[1,2,4,8,16,32].includes(meter[1]),'Invalid meter.');
    return {format:'stemlab.motion-alignment-review.v1',schema_version:1,revision:1,
      previous_revision_sha256:null,report_sha256:entry.report_sha256,
      report_content_sha256:entry.report_content_sha256,
      motion_source_sha256:report.motion_source.sha256,audio_source_sha256:report.audio_source.sha256,
      candidate_id:report.candidates[candidateIndex].candidate_id,decision:'accept_mapping',
      reviewer:reviewer.trim(),reviewed_at:new Date().toISOString(),mapping_status:'user_confirmed',
      mapping_segments:segments,beat_one_audio_seconds:beatOne,
      beat_one_status:beatOne===null?'unconfirmed':'user_confirmed',meter,
      meter_status:meter===null?'unconfirmed':'user_confirmed',
      loop_seams_verified:false,retargeting_verified:false};
  }
  function mount({reviews,getSong,getMotion,canConfirm,onChange}){
    const el=id=>document.getElementById(id),reportSelect=el('timing-report'),candidateSelect=el('timing-candidate');
    let available=[];
    const selected=()=>available[Number(reportSelect.value)];
    const enabled=()=>el('timing-enable').checked&&!!selected();
    const offset=()=>Number(el('timing-offset').value);
    function status(){
      const entry=selected(),candidate=entry?.report.candidates[Number(candidateSelect.value)];
      el('timing-save').disabled=!entry||!canConfirm();
      if(!candidate){el('timing-status').textContent='Add a source-matched StemLab alignment report when building this preview to review timing.';return;}
      try{shiftedSegments(entry,Number(candidateSelect.value),offset());
        el('timing-status').textContent=`${candidate.method.replaceAll('_',' ')} · event agreement ${(candidate.score_uncalibrated*100).toFixed(1)}% · ${entry.report.result_status.replaceAll('_',' ')}. Phase correction ${offset().toFixed(3)} s. Save records your decision separately.`;
      }catch(error){el('timing-status').textContent=error.message;el('timing-save').disabled=true;}
    }
    function candidates(){
      candidateSelect.replaceChildren();const entry=selected();
      for(const [i,c] of (entry?.report.candidates||[]).entries()){
        const option=document.createElement('option');option.value=i;
        option.textContent=`#${i+1} · ${c.method.replaceAll('_',' ')} · ${(c.score_uncalibrated*100).toFixed(1)}% agreement`;
        candidateSelect.append(option);
      }
      candidateSelect.disabled=!entry?.report.candidates?.length;status();
    }
    function refresh(){
      available=matchingReviews(reviews,getSong(),getMotion());reportSelect.replaceChildren();
      for(const [i,x] of available.entries()){
        const option=document.createElement('option');option.value=i;option.textContent=`Timing report ${i+1} · ${x.report_sha256.slice(0,10)}`;reportSelect.append(option);
      }
      reportSelect.disabled=!available.length;el('timing-enable').disabled=!available.length;
      el('timing-enable').checked=false;el('timing-offset').value='0';el('timing-beat-one').value='';el('timing-meter').value='';candidates();
    }
    reportSelect.addEventListener('change',()=>{candidates();onChange()});
    for(const id of ['timing-candidate','timing-offset','timing-enable'])el(id).addEventListener('input',()=>{status();onChange()});
    el('timing-save').addEventListener('click',()=>{
      try{
        require(canConfirm(),'Load the exact audio master before saving a timing decision.');
        const meter=el('timing-meter').value;
        const revision=makeRevision(selected(),Number(candidateSelect.value),{offset:offset(),
          reviewer:el('timing-reviewer').value,beatOne:el('timing-beat-one').value===''?null:Number(el('timing-beat-one').value),
          meter:meter?meter.split('/').map(Number):null});
        const url=URL.createObjectURL(new Blob([JSON.stringify(revision,null,2)+'\n'],{type:'application/json'}));
        const link=document.createElement('a');link.href=url;link.download='motion-alignment-review.json';link.click();
        setTimeout(()=>URL.revokeObjectURL(url),0);
        el('timing-status').textContent='Your timing decision was saved. Original evidence and motion files remain unchanged.';
      }catch(error){el('timing-status').textContent=error.message;}
    });
    return {refresh,status,playbackRange(){
      if(!enabled())return null;
      try{const parts=shiftedSegments(selected(),Number(candidateSelect.value),offset());
        return [parts[0].audio_seconds_range[0],parts.at(-1).audio_seconds_range[1]];}
      catch{return null}
    },motionTime(seconds){
      if(!enabled())return {active:false,value:null};
      try{return {active:true,value:inverseTime(shiftedSegments(selected(),Number(candidateSelect.value),offset()),seconds)}}
      catch{return {active:true,value:null}}
    }};
  }
  globalThis.DanceRudimentsTimingReview={matchingReviews,shiftedSegments,inverseTime,phaseForSource,makeRevision,mount};
})();
