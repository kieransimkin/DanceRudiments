/* Bounded, hash-bound local audition assets; no motion or timing engine. */
(function(root){
  'use strict';
  async function verifiedAsset(descriptor,{fetch:request=root.fetch,signal}={}){
    if(!descriptor || !/^(?:motion-assets\/motion-\d+\.(?:preview|motion)\.json|audio\/[a-z0-9-]+\.mp3)$/.test(descriptor.path)
      || !/^[a-f0-9]{64}$/.test(descriptor.sha256)
      || !Number.isSafeInteger(descriptor.byte_length) || descriptor.byte_length<1 || descriptor.byte_length>32*1024*1024)
      throw Error('Invalid local audition asset identity');
    const response=await request(descriptor.path,{signal,credentials:'same-origin'});
    if(!response.ok || !response.body?.getReader)throw Error('Audition asset unavailable');
    const reader=response.body.getReader(),chunks=[];let length=0;
    try{
      for(;;){const {done,value}=await reader.read();if(done)break;
        length+=value.byteLength;if(length>descriptor.byte_length)throw Error('Audition asset exceeds its bound');chunks.push(value);}
    }catch(error){await reader.cancel().catch(()=>{});throw error;}finally{reader.releaseLock();}
    if(length!==descriptor.byte_length)throw Error('Audition asset length changed');
    const bytes=new Uint8Array(length);let offset=0;
    for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
    if(!root.crypto?.subtle)throw Error('SHA-256 is required for audition assets');
    const digest=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
    if(digest!==descriptor.sha256)throw Error('Audition asset SHA-256 changed');
    return bytes;
  }
  function validatePreview(data,motion){
    if(!data || Object.keys(data).some(key=>!['xyz','frame_relative_pips'].includes(key))
      || !Array.isArray(data.xyz) || data.xyz.length!==motion.frame_count || data.xyz.length>240
      || !Array.isArray(data.frame_relative_pips) || data.frame_relative_pips.length!==data.xyz.length)
      throw Error('Preview frame identity differs');
    let previous=-1;
    for(let i=0;i<data.xyz.length;i++){
      const pip=data.frame_relative_pips[i],frame=data.xyz[i];
      if(!Number.isSafeInteger(pip)||pip<=previous||pip<0||pip>=motion.raw_sample_count
        || !Array.isArray(frame)||frame.length>120||frame.length!==(motion.bones.length||motion.links.length+1)
        || frame.some(point=>!Array.isArray(point)||point.length!==3||point.some(value=>!Number.isFinite(value))))
        throw Error('Invalid bounded source preview');
      previous=pip;
    }
    return data;
  }
  root.DanceRudimentsMotionAssets=Object.freeze({verifiedAsset,validatePreview});
})(globalThis);
