/** Package the existing C++ recording WASM separately from the page loader. */
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const assets = join(root, 'python/dancerudiments_authoring/harness_assets');
const hashes = JSON.parse(await readFile(join(assets, 'recording.wasm.json'), 'utf8'));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
for (const [path, expected] of Object.entries(hashes)) {
  if (path === 'wasm_sha256') continue;
  if (digest(await readFile(join(root, path))) !== expected)
    throw Error(`Recording WASM source changed: ${path}; run tools/build_recording_wasm.py first`);
}
const wasm = Buffer.from(await readFile(join(assets, 'recording.wasm.b64'), 'utf8'), 'base64');
if (digest(wasm) !== hashes.wasm_sha256 || !WebAssembly.validate(wasm))
  throw Error('Checked-in recording WASM is invalid or its SHA-256 differs');
const destination = join(root, 'dist/recording');
await mkdir(destination, {recursive: true});
await writeFile(join(destination, 'recording.wasm'), wasm);
await writeFile(join(destination, 'recording.wasm.json'), JSON.stringify(hashes, null, 2) + '\n');
console.log(`Packaged optional native recording runtime (${wasm.length} bytes).`);
