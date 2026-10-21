/** Optional, scene-owned rig recordings. No assets are fetched at module import. */
export type MotionJson = null | boolean | number | string | readonly MotionJson[] | MotionJsonObject;
export type MotionJsonObject = {readonly [key: string]: MotionJson};

export type MotionPackageAsset = Readonly<{path: string; sha256: string; byte_length: number}>;
export type MotionPackageClip = MotionPackageAsset & Readonly<{
  id: string;
  decoded_byte_length: number;
  encoding: "json" | "gzip";
  start_pip: number;
  sample_count: number;
  metadata?: MotionJsonObject;
}>;
export type MotionPackageManifest = Readonly<{
  format: "dancerudiments.motion-package";
  schema_version: 1;
  id: string;
  version: string;
  title: string;
  type_uri: string;
  profile_sha256: string;
  dimensions: readonly string[];
  profile: MotionPackageAsset;
  clips: readonly MotionPackageClip[];
  license: MotionJsonObject;
  provenance: MotionJsonObject;
}>;
export type MotionRigChannel = Readonly<{
  number: number;
  name: string;
  bone: string;
  data_path: string;
  array_index: number;
  unit: string;
  minimum: number;
  maximum: number;
  neutral: number;
  value_type: "float" | "integer" | "boolean";
  interpolation: "linear" | "step" | "quaternion";
  rotation_mode: string;
  enum_items: readonly (readonly [number, string])[];
}>;
export type MotionRigProfile = Readonly<{
  format: "dancerudiments.rig-profile";
  schema_version: 1;
  type_uri: string;
  model: string;
  version: number;
  channels: readonly MotionRigChannel[];
  source: MotionJsonObject;
}>;
export type MotionRecordingClock = Readonly<{
  bpm: number;
  bpm_source: string;
  bpm_status: "estimated" | "confirmed";
  beat_zero_seconds: number;
  phase_status: "unverified" | "estimated" | "supplied";
  start_pip: number;
}>;
export type MotionRecording = Readonly<{
  format: "dancerudiments.recording";
  schema_version: 1;
  pips_per_beat: 64;
  sample_dtype: "float64";
  sample_decimals: 12;
  name: string;
  dimensions: readonly string[];
  clock: MotionRecordingClock;
  samples: readonly (readonly number[])[];
  provenance: MotionJsonObject;
}>;
export type NativeMotionRecording = Readonly<{
  sample(pip: number): readonly number[];
  dispose(): void;
}>;
export type NativeMotionRecordingFactory = (
  recording: MotionRecording, options: Readonly<{signal: AbortSignal}>,
) => NativeMotionRecording | Promise<NativeMotionRecording>;
export type MotionPackageTarget = Readonly<{
  typeUri: string; sha256: string; dimensions: readonly string[];
}>;
export type MotionLoadOptions = Readonly<{signal?: AbortSignal}>;
export type MotionPackageLoaderOptions = Readonly<{
  manifestUrl: string | URL;
  packageId: string;
  expectedProfile: MotionPackageTarget;
  nativeFactory: NativeMotionRecordingFactory;
  fetch?: typeof fetch;
  manifestSha256?: string;
}>;
export type LoadedRigMotion = Readonly<{
  id: string;
  profile: MotionRigProfile;
  profileSha256: string;
  dimensions: readonly string[];
  clock: MotionRecordingClock;
  startPip: number;
  sampleCount: number;
  metadata: MotionJsonObject;
  readonly disposed: boolean;
  sampleNormalized(pip: number): readonly number[];
  sample(pip: number): readonly (number | boolean)[];
}>;
export type MotionPackageLoader = Readonly<{
  catalogue(options?: MotionLoadOptions): Promise<MotionPackageManifest>;
  load(id: string, options?: MotionLoadOptions): Promise<LoadedRigMotion>;
  unload(id: string): void;
  dispose(): void;
}>;

const MAX_JSON_BYTES = 64 * 1024 * 1024;
const MAX_MANIFEST_BYTES = 8 * 1024 * 1024;
const MAX_VALUES = 8_388_608;
const MAX_CLIPS = 10_000;
const MIN_PIP = -2147483648;
const MAX_PIP = 2147483647;
const ID = /^[a-z][a-z0-9_]{0,127}$/;
const SHA = /^[a-f0-9]{64}$/;
const TYPE = /^syn:\/\/type\/[a-z0-9_-]+(?:\/[a-z0-9_-]+)*$/;
const PATH = /^[A-Za-z0-9_][A-Za-z0-9_.-]*(?:\/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$/;
const RESERVED_PATHS = new Set(["manifest.json", "readme.md", "license.txt", "third_party_notices.md", "sources.json"]);
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*))?(?:\+[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)?$/;

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw Error(`${label} must be an object`);
  return value as Record<string, unknown>;
}
function fields(value: Record<string, unknown>, required: string[], optional: string[], label: string): void {
  const allowed = new Set([...required, ...optional]);
  if (required.some(key => !Object.prototype.hasOwnProperty.call(value, key)) ||
      Object.keys(value).some(key => !allowed.has(key))) throw Error(`Invalid ${label} fields`);
}
function integer(value: unknown, low: number, high: number, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < low || (value as number) > high)
    throw Error(`${label} must be an integer in [${low}, ${high}]`);
  return value as number;
}
function number(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw Error(`${label} must be finite`);
  return value;
}
function string(value: unknown, label: string, max = 4096): string {
  if (typeof value !== "string" || !value.length || value.length > max || value.includes("\0"))
    throw Error(`Invalid ${label}`);
  return value;
}
function identifier(value: unknown, label: string): string {
  const result = string(value, label, 128);
  if (!ID.test(result)) throw Error(`Invalid ${label}`);
  return result;
}
function sha(value: unknown, label: string): string {
  if (typeof value !== "string" || !SHA.test(value)) throw Error(`Invalid ${label} SHA-256`);
  return value;
}
function typeUri(value: unknown): string {
  const result = string(value, "type_uri").replace(/^synny:\/\//, "syn://");
  if (!TYPE.test(result)) throw Error("Invalid semantic type_uri");
  return result;
}
function dimensions(value: unknown): readonly string[] {
  if (!Array.isArray(value) || !value.length || value.length > 1_000_000) throw Error("Invalid dimensions");
  const result = value.map(item => identifier(item, "dimension"));
  if (new Set(result).size !== result.length) throw Error("Duplicate dimensions");
  return Object.freeze(result);
}
function sameDimensions(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}
function json(value: unknown, depth = 0): MotionJson {
  if (depth > 128) throw Error("JSON metadata nesting limit exceeded");
  if (value === null || typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") return number(value, "JSON metadata number");
  if (Array.isArray(value)) return Object.freeze(value.map(item => json(item, depth + 1)));
  const result: {[key: string]: MotionJson} = Object.create(null);
  for (const [key, item] of Object.entries(object(value, "JSON metadata"))) result[key] = json(item, depth + 1);
  return Object.freeze(result);
}
function jsonObject(value: unknown, label: string): MotionJsonObject {
  object(value, label);
  return json(value) as MotionJsonObject;
}
function metadata(value: unknown): MotionJsonObject {
  const result = jsonObject(value, "metadata");
  if (result.timing_kind !== undefined && result.timing_kind !== "music" && result.timing_kind !== "time-only")
    throw Error("metadata.timing_kind must be music or time-only");
  return result;
}
function asset(value: unknown): MotionPackageAsset {
  const v = object(value, "asset");
  const path = string(v.path, "asset path", 1024);
  if (!PATH.test(path)) throw Error("Asset path must be a plain relative path without traversal, URL or query");
  if (RESERVED_PATHS.has(path.toLowerCase())) throw Error("Asset path collides with reserved package metadata/notices");
  return Object.freeze({path, sha256: sha(v.sha256, "asset"), byte_length: integer(v.byte_length, 1, MAX_JSON_BYTES, "byte_length")});
}
function validateManifest(value: unknown, packageId: string, target: MotionPackageTarget): MotionPackageManifest {
  const v = object(value, "motion package");
  fields(v, ["format", "schema_version", "id", "version", "title", "type_uri", "profile_sha256", "dimensions", "profile", "clips", "license", "provenance"], [], "motion package");
  if (v.format !== "dancerudiments.motion-package" || v.schema_version !== 1) throw Error("Unsupported motion package format/version");
  const id = identifier(v.id, "package id");
  if (id !== packageId) throw Error("Motion package ID mismatch");
  const version = string(v.version, "package version", 128), match = SEMVER.exec(version);
  if (!match || match[4]?.split(".").some(part => /^\d+$/.test(part) && part.length > 1 && part[0] === "0")) throw Error("Package version must be semver");
  const uri = typeUri(v.type_uri), fingerprint = sha(v.profile_sha256, "profile"), dims = dimensions(v.dimensions);
  if (uri !== target.typeUri || fingerprint !== target.sha256 || !sameDimensions(dims, target.dimensions))
    throw Error("Motion package target profile/type/dimensions mismatch");
  const profile = asset(v.profile);
  fields(object(v.profile, "profile asset"), ["path", "sha256", "byte_length"], [], "profile asset");
  if (profile.sha256 !== fingerprint) throw Error("Canonical profile asset SHA-256 must equal profile fingerprint");
  if (!Array.isArray(v.clips) || !v.clips.length || v.clips.length > MAX_CLIPS) throw Error("Invalid package clip count");
  const ids = new Set<string>(), paths = new Set([profile.path.toLowerCase()]);
  const clips = v.clips.map(item => {
    const c = object(item, "clip");
    fields(c, ["id", "path", "sha256", "byte_length", "decoded_byte_length", "encoding", "start_pip", "sample_count"], ["metadata"], "clip");
    const info = asset(c), clipId = identifier(c.id, "clip id");
    if (ids.has(clipId) || paths.has(info.path.toLowerCase())) throw Error("Duplicate clip ID or asset path");
    ids.add(clipId); paths.add(info.path.toLowerCase());
    if (c.encoding !== "json" && c.encoding !== "gzip") throw Error("Unsupported clip encoding");
    const decoded = integer(c.decoded_byte_length, 1, MAX_JSON_BYTES, "decoded_byte_length");
    if (c.encoding === "json" && decoded !== info.byte_length) throw Error("JSON stored and decoded byte lengths must match");
    const first = integer(c.start_pip, MIN_PIP, MAX_PIP, "start_pip");
    const count = integer(c.sample_count, 1, Math.floor(MAX_VALUES / dims.length), "sample_count");
    if (first + count > MAX_PIP) throw Error("Recording extent exceeds signed int32 pip range");
    return Object.freeze({...info, id: clipId, encoding: c.encoding, decoded_byte_length: decoded,
      start_pip: first, sample_count: count, ...(c.metadata === undefined ? {} : {metadata: metadata(c.metadata)})}) as MotionPackageClip;
  });
  const title = string(v.title, "title", 1024);
  if (!title.trim()) throw Error("Package title must not be blank");
  return Object.freeze({format: "dancerudiments.motion-package", schema_version: 1, id, version,
    title, type_uri: uri, profile_sha256: fingerprint, dimensions: dims, profile,
    clips: Object.freeze(clips), license: jsonObject(v.license, "license"), provenance: jsonObject(v.provenance, "provenance")});
}

function validateProfile(value: unknown, manifest: MotionPackageManifest): MotionRigProfile {
  const v = object(value, "rig profile");
  fields(v, ["format", "schema_version", "type_uri", "model", "version", "channels", "source"], [], "rig profile");
  if (v.format !== "dancerudiments.rig-profile" || v.schema_version !== 1 || typeUri(v.type_uri) !== manifest.type_uri)
    throw Error("Rig profile format/type mismatch");
  if (!Array.isArray(v.channels) || v.channels.length !== manifest.dimensions.length) throw Error("Rig profile dimensions mismatch");
  const bindings = new Set<string>(), modes = new Map<string, string>(), groups = new Map<string, Set<number>>();
  const channels = v.channels.map((item, index) => {
    const c = object(item, "channel");
    fields(c, ["number", "name", "bone", "data_path", "array_index", "unit", "minimum", "maximum", "neutral"], ["value_type", "interpolation", "rotation_mode", "enum_items"], "channel");
    integer(c.number, index + 1, index + 1, "channel number");
    const name = identifier(c.name, "channel name"), bone = string(c.bone, "bone", 1024);
    if (name !== manifest.dimensions[index]) throw Error("Profile channel order does not match dimensions");
    const dataPath = string(c.data_path, "data_path", 2048), arrayIndex = integer(c.array_index, -1, 1024, "array_index");
    const binding = JSON.stringify([bone, dataPath, arrayIndex]);
    if (bindings.has(binding)) throw Error("Duplicate rig channel binding");
    bindings.add(binding);
    const minimum = number(c.minimum, "minimum"), maximum = number(c.maximum, "maximum"), neutral = number(c.neutral, "neutral");
    if (minimum >= maximum || !Number.isFinite(maximum - minimum) || neutral < minimum || neutral > maximum) throw Error("Invalid channel range/neutral");
    const valueType = c.value_type === undefined ? "float" : c.value_type;
    const interpolation = c.interpolation === undefined ? "linear" : c.interpolation;
    const mode = c.rotation_mode === undefined ? "" : c.rotation_mode;
    if (!["float", "integer", "boolean"].includes(valueType as string) || !["linear", "step", "quaternion"].includes(interpolation as string)) throw Error("Unsupported channel value/interpolation type");
    if (valueType !== "float" && (interpolation !== "step" || ![minimum, maximum, neutral].every(Number.isSafeInteger) || maximum - minimum > 1e11)) throw Error("Invalid discrete channel range/interpolation");
    if (valueType === "boolean" && (minimum !== 0 || maximum !== 1)) throw Error("Boolean channels require range [0,1]");
    if (!["", "QUATERNION", "AXIS_ANGLE", "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"].includes(mode as string)) throw Error("Unsupported rotation mode");
    if (mode) {
      if (modes.has(bone) && modes.get(bone) !== mode) throw Error("Inconsistent rotation modes for control bone");
      modes.set(bone, mode as string);
    }
    const enumItems = c.enum_items === undefined ? [] : c.enum_items;
    if (!Array.isArray(enumItems)) throw Error("Invalid enum_items");
    const choices = new Set<number>();
    const enums = enumItems.map(item => {
      if (!Array.isArray(item) || item.length !== 2 || valueType !== "integer") throw Error("Invalid enum item");
      const choice = integer(item[0], minimum, maximum, "enum value"), label = string(item[1], "enum label", 1024);
      if (choices.has(choice)) throw Error("Duplicate enum choice");
      choices.add(choice);
      return Object.freeze([choice, label]) as readonly [number, string];
    });
    if (choices.size && !choices.has(neutral)) throw Error("Enum neutral must be a declared choice");
    if (dataPath === "rotation_quaternion" && interpolation !== "quaternion") throw Error("Quaternion channels require grouped interpolation");
    if (interpolation === "quaternion") {
      if (dataPath !== "rotation_quaternion" || mode !== "QUATERNION" || arrayIndex < 0 || arrayIndex > 3 || minimum !== -1 || maximum !== 1) throw Error("Invalid quaternion channel");
      if (!groups.has(bone)) groups.set(bone, new Set());
      groups.get(bone)!.add(arrayIndex);
    }
    return Object.freeze({number: index + 1, name, bone, data_path: dataPath, array_index: arrayIndex,
      unit: string(c.unit, "unit", 128), minimum, maximum, neutral, value_type: valueType,
      interpolation, rotation_mode: mode, enum_items: Object.freeze(enums)}) as MotionRigChannel;
  });
  for (const group of groups.values()) if (group.size !== 4) throw Error("Quaternion controls require all four wxyz channels");
  return Object.freeze({format: "dancerudiments.rig-profile", schema_version: 1, type_uri: manifest.type_uri,
    model: string(v.model, "model", 1024), version: integer(v.version, 1, Number.MAX_SAFE_INTEGER, "profile version"),
    channels: Object.freeze(channels), source: jsonObject(v.source, "profile source")});
}

function decoder(profile: MotionRigProfile): (row: readonly number[]) => readonly (number | boolean)[] {
  const groups = new Map<string, number[]>();
  const choices = profile.channels.map(channel => new Set(channel.enum_items.map(item => item[0])));
  profile.channels.forEach((channel, index) => {
    if (channel.interpolation === "quaternion") {
      if (!groups.has(channel.bone)) groups.set(channel.bone, []);
      groups.get(channel.bone)!.push(index);
    }
  });
  return row => {
    const result = profile.channels.map((channel, index): number | boolean => {
      const value = channel.minimum + (row[index] + 1) * 0.5 * (channel.maximum - channel.minimum);
      if (channel.value_type === "float") return value;
      const nearest = Math.round(value), tolerance = Math.max(1e-9, (channel.maximum - channel.minimum) * 1e-12);
      if (Math.abs(value - nearest) > tolerance || (choices[index].size && !choices[index].has(nearest)))
        throw Error(`Invalid discrete value for channel ${channel.name}`);
      return channel.value_type === "boolean" ? Boolean(nearest) : nearest;
    });
    for (const indices of groups.values()) {
      const norm = Math.hypot(...indices.map(index => result[index] as number));
      if (Math.abs(norm - 1) > 1e-5) throw Error("Recorded quaternion must have unit length");
    }
    return Object.freeze(result);
  };
}

function validateRecording(value: unknown, clip: MotionPackageClip, manifest: MotionPackageManifest, profile: MotionRigProfile): MotionRecording {
  const v = object(value, "recording");
  fields(v, ["format", "schema_version", "pips_per_beat", "sample_dtype", "sample_decimals", "name", "dimensions", "clock", "samples", "provenance"], [], "recording");
  if (v.format !== "dancerudiments.recording" || v.schema_version !== 1 || v.pips_per_beat !== 64 || v.sample_dtype !== "float64" || v.sample_decimals !== 12)
    throw Error("Unsupported recording format/precision/clock");
  if (v.name !== clip.id) throw Error("Recording name does not match clip ID");
  const dims = dimensions(v.dimensions);
  if (!sameDimensions(dims, manifest.dimensions)) throw Error("Recording dimensions/order do not match the rig profile");
  const c = object(v.clock, "clock");
  fields(c, ["bpm", "bpm_source", "bpm_status", "beat_zero_seconds", "phase_status", "start_pip"], [], "recording clock");
  const bpm = number(c.bpm, "BPM"), source = string(c.bpm_source, "bpm_source");
  if (bpm <= 0 || !Number.isFinite(60 / bpm) || 60 / bpm / 64 <= 0 || !source.trim()) throw Error("A positive representable BPM and provenance are required");
  if (c.bpm_status !== "confirmed" && c.bpm_status !== "estimated") throw Error("Invalid bpm_status");
  if (c.phase_status !== "unverified" && c.phase_status !== "estimated" && c.phase_status !== "supplied") throw Error("Invalid phase_status");
  if (c.start_pip !== clip.start_pip) throw Error("Recording start_pip does not match manifest");
  const clock = Object.freeze({bpm, bpm_source: source, bpm_status: c.bpm_status,
    beat_zero_seconds: number(c.beat_zero_seconds, "beat_zero_seconds"), phase_status: c.phase_status, start_pip: clip.start_pip});
  if (!Array.isArray(v.samples) || v.samples.length !== clip.sample_count) throw Error("Recording sample_count does not match manifest");
  const decode = decoder(profile);
  for (const row of v.samples) {
    if (!Array.isArray(row) || row.length !== dims.length) throw Error("Ragged recording sample dimensions");
    for (const value of row) {
      if (typeof value !== "number" || !Number.isFinite(value) || Math.abs(value) > 1 || Number(value.toFixed(12)) !== value)
        throw Error("Samples must be finite normalized float64 values rounded to twelve decimals");
    }
    decode(row);
    Object.freeze(row);
  }
  return Object.freeze({format: "dancerudiments.recording", schema_version: 1, pips_per_beat: 64,
    sample_dtype: "float64", sample_decimals: 12, name: clip.id, dimensions: dims, clock,
    samples: Object.freeze(v.samples as number[][]), provenance: jsonObject(v.provenance, "recording provenance")});
}

function abortError(): Error { return new DOMException("Motion loading was aborted", "AbortError"); }
function checkAbort(signal: AbortSignal): void { if (signal.aborted) throw abortError(); }

// JSON.parse discards duplicate keys. Scan object keys first so profile identity
// and clock declarations cannot be silently overwritten by a later field.
function parseJson(bytes: Uint8Array): unknown {
  const text = new TextDecoder("utf-8", {fatal: true}).decode(bytes);
  const stack: ({keys: Set<string>; key: boolean} | null)[] = [];
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (char === '"') {
      const start = index++;
      while (index < text.length && text[index] !== '"') { if (text[index] === "\\") index++; index++; }
      if (index >= text.length) throw Error("Unterminated JSON string");
      const current = stack[stack.length - 1];
      if (current?.key) {
        const key = JSON.parse(text.slice(start, index + 1)) as string;
        if (current.keys.has(key)) throw Error(`Duplicate JSON key: ${key}`);
        current.keys.add(key); current.key = false;
      }
    } else if (char === "{" || char === "[") {
      stack.push(char === "{" ? {keys: new Set(), key: true} : null);
      if (stack.length > 128) throw Error("JSON nesting limit exceeded");
    } else if (char === "}" || char === "]") stack.pop();
    else if (char === "," && stack[stack.length - 1]) stack[stack.length - 1]!.key = true;
  }
  return JSON.parse(text);
}

async function readBytes(stream: ReadableStream<Uint8Array>, limit: number, signal: AbortSignal): Promise<Uint8Array<ArrayBuffer>> {
  checkAbort(signal);
  const reader = stream.getReader(), chunks: Uint8Array[] = [];
  let size = 0;
  const cancel = (): void => { void reader.cancel(abortError()).catch(() => {}); };
  signal.addEventListener("abort", cancel, {once: true});
  try {
    while (true) {
      const next = await reader.read();
      checkAbort(signal);
      if (next.done) break;
      size += next.value.byteLength;
      if (size > limit) { await reader.cancel(); throw Error("Asset exceeds declared byte length/resource limit"); }
      chunks.push(next.value);
    }
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
    return result;
  } finally { signal.removeEventListener("abort", cancel); reader.releaseLock(); }
}
async function digest(bytes: Uint8Array): Promise<string> {
  if (!globalThis.crypto?.subtle) throw Error("SHA-256 verification requires Web Crypto in a secure context");
  const hash = await crypto.subtle.digest("SHA-256", new Uint8Array(bytes));
  return Array.from(new Uint8Array(hash), item => item.toString(16).padStart(2, "0")).join("");
}
async function fetchBytes(fetcher: typeof fetch, url: URL, limit: number, signal: AbortSignal, expected?: MotionPackageAsset): Promise<Uint8Array<ArrayBuffer>> {
  checkAbort(signal);
  const response = await fetcher(url, {signal, credentials: "omit"});
  if (signal.aborted) await response.body?.cancel();
  checkAbort(signal);
  if (!response.ok) { await response.body?.cancel(); throw Error(`Motion asset HTTP ${response.status}: ${url.pathname}`); }
  if (!response.body) throw Error("Motion asset has no readable response body");
  const length = response.headers.get("content-length");
  if (length && /^\d+$/.test(length) && Number(length) > limit) {
    await response.body.cancel(); throw Error("Motion asset Content-Length exceeds resource limit");
  }
  const bytes = await readBytes(response.body, limit, signal);
  if (expected && bytes.byteLength !== expected.byte_length) throw Error("Motion asset byte length mismatch");
  if (expected && await digest(bytes) !== expected.sha256) throw Error("Motion asset SHA-256 integrity mismatch");
  checkAbort(signal);
  return bytes;
}

type Entry<T> = {controller: AbortController; promise: Promise<T>; waiters: number; settled: boolean; value?: T};
function removeEntry<T>(cache: Map<string, Entry<T>>, key: string, drop: (value: T) => void): void {
  const entry = cache.get(key);
  if (!entry) return;
  cache.delete(key);
  entry.controller.abort();
  if (entry.value !== undefined) { const value = entry.value; entry.value = undefined; drop(value); }
}
function acquire<T>(cache: Map<string, Entry<T>>, key: string, signal: AbortSignal | undefined,
                    work: (signal: AbortSignal) => Promise<T>, drop: (value: T) => void): Promise<T> {
  if (signal?.aborted) return Promise.reject(abortError());
  let entry = cache.get(key);
  if (!entry) {
    const created: Entry<T> = {controller: new AbortController(), promise: undefined as unknown as Promise<T>, waiters: 0, settled: false};
    created.promise = Promise.resolve().then(() => work(created.controller.signal)).then(value => {
      if (cache.get(key) !== created || created.controller.signal.aborted) { drop(value); throw abortError(); }
      created.value = value; created.settled = true; return value;
    }, error => {
      if (cache.get(key) === created) cache.delete(key);
      created.settled = true;
      throw error;
    });
    cache.set(key, created); entry = created;
  }
  const current = entry;
  current.waiters++;
  return new Promise<T>((resolve, reject) => {
    let finished = false;
    const finish = (success: boolean, result: unknown): void => {
      if (finished) return;
      finished = true;
      signal?.removeEventListener("abort", cancelled);
      current.controller.signal.removeEventListener("abort", cancelled);
      current.waiters--;
      if (success) resolve(result as T); else reject(result);
      if (!current.waiters && !current.settled && cache.get(key) === current) removeEntry(cache, key, drop);
    };
    const cancelled = (): void => finish(false, abortError());
    signal?.addEventListener("abort", cancelled, {once: true});
    current.controller.signal.addEventListener("abort", cancelled, {once: true});
    if (signal?.aborted || current.controller.signal.aborted) cancelled();
    current.promise.then(value => finish(true, value), error => finish(false, error));
  });
}

/** Construct an inert loader owned by one page/scene. No global motion registry. */
export function createMotionPackageLoader(options: MotionPackageLoaderOptions): MotionPackageLoader {
  const packageId = identifier(options.packageId, "packageId");
  const target = Object.freeze({typeUri: typeUri(options.expectedProfile.typeUri), sha256: sha(options.expectedProfile.sha256, "expected profile"), dimensions: dimensions(options.expectedProfile.dimensions)});
  const url = new URL(options.manifestUrl, typeof location === "undefined" ? undefined : location.href);
  if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || url.hash) throw Error("Manifest URL must be an HTTP(S) URL without credentials/fragment");
  if (typeof options.nativeFactory !== "function") throw Error("A native recording factory is required");
  const nativeFactory = options.nativeFactory;
  const fetcher = options.fetch ?? globalThis.fetch?.bind(globalThis);
  if (!fetcher) throw Error("A fetch implementation is required");
  const manifestHash = options.manifestSha256 === undefined ? undefined : sha(options.manifestSha256, "manifest");
  const manifests = new Map<string, Entry<MotionPackageManifest>>();
  const profiles = new Map<string, Entry<MotionRigProfile>>();
  const clips = new Map<string, Entry<{handle: LoadedRigMotion; dispose(): void}>>();
  const noDrop = (): void => {};
  const dropClip = (value: {dispose(): void}): void => value.dispose();
  let disposed = false;
  const active = (): void => { if (disposed) throw Error("Motion package loader is disposed"); };
  const getManifest = (signal?: AbortSignal): Promise<MotionPackageManifest> => acquire(manifests, "manifest", signal, async current => {
    const bytes = await fetchBytes(fetcher, url, MAX_MANIFEST_BYTES, current);
    if (manifestHash && await digest(bytes) !== manifestHash) throw Error("Manifest SHA-256 integrity mismatch");
    checkAbort(current);
    return validateManifest(parseJson(bytes), packageId, target);
  }, noDrop);
  const getProfile = (manifest: MotionPackageManifest, signal: AbortSignal): Promise<MotionRigProfile> => acquire(profiles, "profile", signal, async current => {
    const bytes = await fetchBytes(fetcher, new URL(manifest.profile.path, url), manifest.profile.byte_length, current, manifest.profile);
    if (bytes.some(value => value > 127)) throw Error("Canonical rig profile must use ASCII JSON bytes");
    return validateProfile(parseJson(bytes), manifest);
  }, noDrop);
  return Object.freeze({
    async catalogue(request: MotionLoadOptions = {}): Promise<MotionPackageManifest> {
      active(); return getManifest(request.signal);
    },
    async load(id: string, request: MotionLoadOptions = {}): Promise<LoadedRigMotion> {
      active(); identifier(id, "clip id");
      const loaded = await acquire(clips, id, request.signal, async signal => {
        const manifest = await getManifest(signal);
        const clip = manifest.clips.find(item => item.id === id);
        if (!clip) throw Error(`Unknown motion clip: ${id}`);
        const profile = await getProfile(manifest, signal);
        let bytes = await fetchBytes(fetcher, new URL(clip.path, url), clip.byte_length, signal, clip);
        if (clip.encoding === "gzip") {
          if (typeof DecompressionStream === "undefined") throw Error("Gzip clips require DecompressionStream support");
          const stored = bytes;
          const stream = new ReadableStream<BufferSource>({start(controller) { controller.enqueue(stored); controller.close(); }});
          bytes = await readBytes(stream.pipeThrough(new DecompressionStream("gzip")), clip.decoded_byte_length, signal);
        }
        if (bytes.byteLength !== clip.decoded_byte_length) throw Error("Decoded motion byte length mismatch");
        const recording = validateRecording(parseJson(bytes), clip, manifest, profile);
        checkAbort(signal);
        const native = await nativeFactory(recording, {signal});
        if (!native || typeof native.sample !== "function" || typeof native.dispose !== "function") {
          if (native && typeof native.dispose === "function") native.dispose();
          throw Error("Native recording factory returned an invalid handle");
        }
        if (signal.aborted) { native.dispose(); throw abortError(); }
        const count = clip.sample_count, first = clip.start_pip, clock = recording.clock;
        const decode = decoder(profile);
        let live: NativeMotionRecording | undefined = native;
        const sampleNormalized = (pip: number): readonly number[] => {
          if (!live) throw Error("Rig motion was unloaded/disposed");
          integer(pip, MIN_PIP, MAX_PIP, "pip");
          if (pip < first || pip - first >= count) throw Error("Pip outside non-looping rig motion");
          const row = live.sample(pip);
          if (row.length !== manifest.dimensions.length || Array.from(row).some(value => !Number.isFinite(value) || Math.abs(value) > 1))
            throw Error("Native recording returned invalid dimensions/values");
          return Object.freeze(Array.from(row));
        };
        const handle: LoadedRigMotion = Object.freeze({id, profile, profileSha256: manifest.profile_sha256,
          dimensions: manifest.dimensions, clock, startPip: first, sampleCount: count,
          metadata: clip.metadata ?? Object.freeze({}), get disposed() { return !live; }, sampleNormalized,
          sample: (pip: number) => decode(sampleNormalized(pip))});
        return {handle, dispose() { const previous = live; live = undefined; previous?.dispose(); }};
      }, dropClip);
      return loaded.handle;
    },
    unload(id: string): void { identifier(id, "clip id"); removeEntry(clips, id, dropClip); },
    dispose(): void {
      if (disposed) return;
      disposed = true;
      let failed = false, failure: unknown;
      for (const key of [...clips.keys()]) {
        try { removeEntry(clips, key, dropClip); } catch (error) { if (!failed) failure = error; failed = true; }
      }
      for (const key of [...profiles.keys()]) removeEntry(profiles, key, noDrop);
      for (const key of [...manifests.keys()]) removeEntry(manifests, key, noDrop);
      if (failed) throw failure;
    },
  });
}

/** Use the existing recording_wasm.cpp runtime, supplied explicitly by the app.
 * Each clip owns an isolated WASM memory, released when its handle is disposed.
 * Compilation/fetching of the module is an explicit caller operation.
 */
export function createRecordingWasmAdapter(module: WebAssembly.Module): NativeMotionRecordingFactory {
  if (!(module instanceof WebAssembly.Module)) throw Error("A compiled recording WebAssembly.Module is required");
  return async (recording, {signal}) => {
    checkAbort(signal);
    const instance = await WebAssembly.instantiate(module, {});
    checkAbort(signal);
    const exports = instance.exports;
    if (!(exports.memory instanceof WebAssembly.Memory) || typeof exports.table_base !== "function" || typeof exports.sample_recording !== "function")
      throw Error("WASM module lacks the native recording sampler exports");
    type Api = {memory: WebAssembly.Memory; table_base(): number; sample_recording(base: number, count: number, dimensions: number, first: number, pip: number, axis: number): number};
    let api: Api | undefined = exports as unknown as Api;
    const width = recording.dimensions.length, count = recording.samples.length, first = recording.clock.start_pip;
    integer(width, 1, MAX_VALUES, "native dimensions");
    integer(count, 1, Math.floor(MAX_VALUES / width), "native sample_count");
    integer(first, MIN_PIP, MAX_PIP - count, "native start_pip");
    const base = integer(api.table_base(), 0, MAX_JSON_BYTES, "native table base");
    if (base % 8) throw Error("Native recording table is not float64-aligned");
    const length = count * width * 8, pages = Math.ceil((base + length - api.memory.buffer.byteLength) / 65536);
    if (pages > 0) api.memory.grow(pages);
    // WASM memory is little endian, regardless of the host's typed-array order.
    const view = new DataView(api.memory.buffer, base, length);
    let offset = 0;
    for (const row of recording.samples) {
      if (row.length !== width) throw Error("Ragged native recording");
      for (const value of row) {
        if (!Number.isFinite(value) || Math.abs(value) > 1) throw Error("Invalid native recording value");
        view.setFloat64(offset, value, true); offset += 8;
      }
    }
    return Object.freeze({
      sample(pip: number): readonly number[] {
        if (!api) throw Error("Native recording is disposed");
        integer(pip, MIN_PIP, MAX_PIP, "pip");
        if (pip < first || pip - first >= count) throw Error("Pip outside non-looping native recording");
        const row = Array.from({length: width}, (_, axis) => api!.sample_recording(base, count, width, first, pip, axis));
        if (row.some(value => !Number.isFinite(value) || Math.abs(value) > 1)) throw Error("Native recording sampler returned invalid values");
        return Object.freeze(row);
      },
      dispose(): void { api = undefined; },
    });
  };
}
