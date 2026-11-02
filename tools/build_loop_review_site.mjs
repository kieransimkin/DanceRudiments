#!/usr/bin/env node
/** Build an explicitly prepared local authoring scene with the shared Kandi UI. */
import {build} from 'esbuild';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir, copyFile, lstat, realpath, readdir, mkdtemp, rename, rm} from 'node:fs/promises';
import {resolve, join, dirname, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';

const ROOT=fileURLToPath(new URL('../',import.meta.url));
const sha=data=>createHash('sha256').update(data).digest('hex');
const json=value=>JSON.stringify(value,null,2)+'\n';
const safe=name=>typeof name==='string'&&/^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(name)
  &&!name.split('/').some(p=>p==='.'||p==='..');
async function files(root,prefix=''){
  const result=[];
  for(const item of (await readdir(join(root,prefix),{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))){
    const path=prefix?`${prefix}/${item.name}`:item.name;
    if(item.isSymbolicLink())throw Error('Review assets cannot be symlinks');
    if(item.isDirectory())result.push(...await files(root,path));
    else if(item.isFile())result.push(path);
  }
  return result;
}
export function validateCollectionScenes(config,inventory){
  const ids=new Set();
  for(const scene of config.scenes){
    if(typeof scene.id!=='string'||!/^source-[a-f0-9]{64}$/.test(scene.id)||ids.has(scene.id)
      ||scene.id!==`source-${scene.sourceSha256}`||!safe(scene.rigPath)||!safe(scene.manifestPath)
      ||scene.sceneRigSha256!==inventory.files[scene.rigPath]?.sha256
      ||scene.manifestSha256!==inventory.files[scene.manifestPath]?.sha256
      ||config.auditionCalibrations?.[scene.id]?.source_rig_sha256!==scene.sceneRigSha256
      ||config.auditionCalibrations[scene.id].target_rig_sha256!==config.auditionTargets?.[scene.id]?.rig_sha256
      ||config.auditionTargets[scene.id].asset_sha256!==config.character.fbxAssetSha256
      ||!/^[a-f0-9]{64}$/.test(scene.expectedProfile?.fingerprint||''))
      throw Error('Collection source, rig or calibration identity differs');
    ids.add(scene.id);
  }
}
export async function buildLoopReviewSite(assetsDir,outputDir,{collectionAudition=false}={}){
  const source=await realpath(resolve(assetsDir)),output=resolve(outputDir);
  if(output===source||source.startsWith(output+sep)||output===ROOT)throw Error('Unsafe review-site output');
  try{await lstat(output);throw Error('Review-site output must be new');}catch(error){if(error.code!=='ENOENT')throw error;}
  const config=JSON.parse(await readFile(join(source,'config.json'),'utf8'));
  const inventory=JSON.parse(await readFile(join(source,'assets.json'),'utf8'));
  const validMode=collectionAudition
    ? config.collectionAudition===true&&config.reviewWorkspace===false&&config.scenes?.length>=1&&config.scenes.length<=128
    : config.reviewWorkspace===true&&config.scenes?.length===1;
  if(!validMode||inventory.format!=='dancerudiments.loop-review-assets.v1')
    throw Error('An explicitly prepared review workspace is required');
  const retargetHash=sha(await readFile(join(ROOT,'tools/mesh_demo_assets/kandi-boom.js')));
  const evidence=collectionAudition?config.scenes.map(scene=>config.auditionCalibrations?.[scene.id]):[config.reviewCalibrationEvidence];
  if(evidence.some(item=>item?.retarget_implementation_sha256!==retargetHash))
    throw Error('Retarget implementation changed after the source calibration was prepared');
  if(collectionAudition)validateCollectionScenes(config,inventory);
  const pkg=JSON.parse(await readFile(join(ROOT,'package.json'),'utf8')),versions={};
  for(const name of ['esbuild','three']){
    const actual=JSON.parse(await readFile(join(ROOT,'node_modules',name,'package.json'),'utf8')).version;
    if(actual!==pkg.devDependencies[name])throw Error(`Run npm ci for the exact ${name} dependency`);
    versions[name]=actual;
  }
  await mkdir(dirname(output),{recursive:true});
  const parent=await mkdtemp(join(dirname(output),'.loop-review-site-')),stage=join(parent,'site');
  try{
    const probe=join(parent,'probe');await writeFile(probe,'review-site');
    if(await readFile(probe,'utf8')!=='review-site')throw Error('Temporary-directory read failed');
    await rename(probe,probe+'.renamed');await rm(probe+'.renamed');
    await mkdir(stage);
    for(const [name,desc] of Object.entries(inventory.files)){
      if(!safe(name))throw Error('Unsafe review asset path');
      const path=join(source,name),actual=await realpath(path),stat=await lstat(path);
      if(!actual.startsWith(source+sep)||stat.isSymbolicLink()||!stat.isFile()||stat.size>64*1024*1024)
        throw Error('Invalid review asset');
      const bytes=await readFile(path);
      if(bytes.length!==desc.byte_length||sha(bytes)!==desc.sha256)throw Error(`Review asset changed: ${name}`);
      await mkdir(dirname(join(stage,name)),{recursive:true});await writeFile(join(stage,name),bytes);
    }
    execFileSync(process.execPath,[join(ROOT,'tools/package_recording_runtime.mjs')],{cwd:ROOT,stdio:'pipe'});
    const wasm=await readFile(join(ROOT,'dist/recording/recording.wasm'));
    const native=JSON.parse(await readFile(join(ROOT,'dist/recording/recording.wasm.json'),'utf8'));
    if(sha(wasm)!==native.wasm_sha256||!WebAssembly.validate(wasm))throw Error('Native recording identity failed');
    config.recordingWasm={sha256:sha(wasm),byte_length:wasm.length};
    const commit=execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim();
    const dirty=Boolean(execFileSync('git',['status','--porcelain','--untracked-files=normal'],{cwd:ROOT,encoding:'utf8'}).trim());
    config.build={version:pkg.version,commit,workingTreeDirty:dirty,renderer:versions,nativeRuntime:native};
    await writeFile(join(stage,'recording.wasm'),wasm);
    await writeFile(join(stage,'recording.wasm.json'),json(native));
    for(const name of ['index.html','style.css'])await copyFile(join(ROOT,'tools/mesh_demo_assets',name),join(stage,name));
    await copyFile(join(ROOT,'node_modules/three/LICENSE'),join(stage,'THREE-LICENSE.txt'));
    await copyFile(join(ROOT,'LICENSE'),join(stage,'RUNTIME-LICENSE.txt'));
    const bundle=await build({absWorkingDir:ROOT,entryPoints:[join(ROOT,'tools/mesh_demo_assets/app.js')],outdir:stage,
      bundle:true,splitting:true,format:'esm',platform:'browser',target:['es2022'],charset:'utf8',minify:true,
      legalComments:'linked',entryNames:'app',chunkNames:'chunks/[name]-[hash]',sourcemap:false,metafile:true,
      define:{__MESH_DEMO_CONFIG__:JSON.stringify(config)},logLevel:'silent'});
    if(Object.values(bundle.metafile.outputs).some(f=>f.imports.some(i=>i.external)))throw Error('External browser imports are forbidden');
    const outputFiles={};for(const name of await files(stage)){
      const bytes=await readFile(join(stage,name));outputFiles[name]={sha256:sha(bytes),byte_length:bytes.length};
    }
    const receipt={format:collectionAudition?'dancerudiments.collection-audition-site.v1':'dancerudiments.loop-review-site.v1',schema_version:1,...config.build,
      scope:collectionAudition?'local-read-only-audition':'local-authoring-only',scene_id:config.scenes[0].id,
      target:config.reviewTarget,files:outputFiles,
      ...(collectionAudition?{scenes:config.scenes.map(scene=>({id:scene.id,source_sha256:scene.sourceSha256,profile_sha256:scene.expectedProfile.fingerprint,title:scene.title})),unavailable:config.unavailable}: {})};
    await writeFile(join(stage,'build.json'),json(receipt));
    await rename(stage,output);
    return {output_dir:output,file_count:Object.keys(outputFiles).length+1,commit,working_tree_dirty:dirty};
  }finally{await rm(parent,{recursive:true,force:true});}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const {values}=parseArgs({options:{'assets-dir':{type:'string'},'output-dir':{type:'string'},'collection-audition':{type:'boolean',default:false}},strict:true});
  if(!values['assets-dir']||!values['output-dir'])throw Error('--assets-dir and --output-dir are required');
  buildLoopReviewSite(values['assets-dir'],values['output-dir'],{collectionAudition:values['collection-audition']}).then(result=>console.log(json(result)))
    .catch(error=>{console.error(error.message);process.exitCode=1;});
}
