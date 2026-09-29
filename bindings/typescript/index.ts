import { approvedDefaults, ApprovedDefaultName } from "./defaults.js";

export type Offset3 = Readonly<{ x: number; y: number; z: number }>;
export type RudimentName = "bounce" | "sway" | "circle" | "figure_eight" | "step_touch" | "box_step" | "helix" | "clay_background" | "single_stroke_roll" | "double_stroke_roll" | "multiple_bounce_roll" | "single_paradiddle" | "flam" | "drag" | "five_stroke_roll" | ApprovedDefaultName;
export type RudimentInfo = Readonly<{ name: RudimentName; description: string; periodPips: number; dimensions: 1 | 2 | 3 }>;
type NativeDeletable = { delete(): void };
type NativeOffsets = NativeDeletable & { push_back(value: Offset3): void };
type NativePattern = NativeDeletable;
type NativeLibrary = NativeDeletable & { sample(name: string, pipCount: number): Offset3 };
type NativeModule = {
  sample(name: string, pipCount: number): Offset3;
  OffsetVector?: new () => NativeOffsets;
  SampledPattern?: new (name: string, description: string, values: NativeOffsets) => NativePattern;
  PatternLibrary?: new (patterns: NativePattern[]) => NativeLibrary;
};

// Widen metadata before spreading thousands of literal records. Keep the name
// union precise, without asking TypeScript to construct a huge object union.
const generatedCatalogue: readonly RudimentInfo[] = approvedDefaults;

export const catalogue: readonly RudimentInfo[] = [
  { name: "bounce", description: "One-beat vertical bounce", periodPips: 64, dimensions: 1 },
  { name: "sway", description: "Two-beat side-to-side sway", periodPips: 128, dimensions: 1 },
  { name: "circle", description: "One-beat circular orbit", periodPips: 64, dimensions: 2 },
  { name: "figure_eight", description: "Two-beat figure eight", periodPips: 128, dimensions: 2 },
  { name: "step_touch", description: "Two-beat side step with a small lift", periodPips: 128, dimensions: 2 },
  { name: "box_step", description: "Four-beat softened square path", periodPips: 256, dimensions: 2 },
  { name: "helix", description: "Four-beat double-turn helix", periodPips: 256, dimensions: 3 },
  { name: "clay_background", description: "Clay/Stars four-beat accented background drift", periodPips: 256, dimensions: 2 },
  { name: "single_stroke_roll", description: "Alternating R/L strokes with smooth attack and decay", periodPips: 64, dimensions: 2 },
  { name: "double_stroke_roll", description: "RRLL strokes with a softer second motion", periodPips: 64, dimensions: 2 },
  { name: "multiple_bounce_roll", description: "Decaying same-hand bounce clusters", periodPips: 64, dimensions: 2 },
  { name: "single_paradiddle", description: "RLRR LRLL with accented lead strokes", periodPips: 128, dimensions: 2 },
  { name: "flam", description: "Grace motion flowing into an opposite-hand primary motion", periodPips: 64, dimensions: 2 },
  { name: "drag", description: "Two grace motions flowing into an opposite-hand primary motion", periodPips: 64, dimensions: 2 },
  { name: "five_stroke_roll", description: "Two diddles resolving to an accented fifth motion", periodPips: 128, dimensions: 2 },
  ...generatedCatalogue
];

let native: NativeModule | undefined;
export function bindNative(module: NativeModule): void { native = module; }
export function sample(name: RudimentName, pipCount: number): Offset3 {
  if (!native) throw new Error("DanceRudiments WASM is not bound. Call bindNative(await createDanceRudiments()).");
  validatePip(pipCount);
  return native.sample(name, pipCount);
}

export type PatternInfo = Readonly<{
  name: string; description: string; periodPips: number; dimensions: 1 | 2 | 3;
}>;
export type PatternLibraryHandle = Readonly<{
  sample(name: string, pipCount: number): Offset3;
  catalogue(): readonly PatternInfo[];
  dispose(): void;
}>;

function validatePip(pip: number): void {
  if (!Number.isInteger(pip) || pip < -2147483648 || pip > 2147483647)
    throw new RangeError("pipCount must be a signed 32-bit integer");
}
function object(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new TypeError(`${path} must be an object`);
  return value as Record<string, unknown>;
}

/** Load compiled JSON into a private C++ bank. No JavaScript motion fallback. */
export function createPatternLibrary(document: unknown): PatternLibraryHandle {
  const module = native;
  if (!module?.OffsetVector || !module.SampledPattern || !module.PatternLibrary)
    throw new Error("Bind a DanceRudiments WASM build with sampled-pattern support first.");
  const pack = object(document, "pack");
  if (pack.format !== "dancerudiments.compiled-pack" || pack.schema_version !== 1 || pack.pips_per_beat !== 64)
    throw new TypeError("Unsupported compiled pack format/version/pip resolution");
  if (!Array.isArray(pack.patterns) || pack.patterns.length < 1 || pack.patterns.length > 1024)
    throw new RangeError("A compiled pack requires 1..1024 patterns");
  const names = new Set<string>(catalogue.map(p => p.name));
  const info: PatternInfo[] = [...catalogue];
  const packNames = new Set<string>();
  let total = 0;
  // Validate the entire document before allocating native objects.
  const checked = pack.patterns.map((value: unknown) => {
    const p = object(value, "pattern");
    if (typeof p.name !== "string" || !/^[a-z][a-z0-9_]{0,127}$/.test(p.name) || packNames.has(p.name))
      throw new TypeError("Invalid or duplicate pattern name");
    names.add(p.name);
    packNames.add(p.name);
    if (typeof p.description !== "string" || p.description.includes("\0"))
      throw new TypeError("Pattern description must be a string without NUL characters");
    if (typeof p.period_pips !== "number" || !Number.isInteger(p.period_pips) || p.period_pips < 1 || p.period_pips > 65535)
      throw new RangeError("Pattern period must be an integer in [1, 65535]");
    total += p.period_pips;
    if (total > 1048576) throw new RangeError("Compiled pack exceeds the total sample limit");
    if (!Array.isArray(p.samples) || p.samples.length !== p.period_pips)
      throw new TypeError("Sample count does not match period_pips");
    if (typeof p.source_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(p.source_sha256))
      throw new TypeError("Missing or invalid source_sha256");
    object(p.provenance, "provenance");
    object(p.diagnostics, "diagnostics");
    let dimensions: 1 | 2 | 3 = 1;
    const samples: Offset3[] = p.samples.map((row: unknown) => {
      if (!Array.isArray(row) || row.length !== 3 || row.some(v => typeof v !== "number" || !Number.isFinite(v) || Math.abs(v) > 1))
        throw new TypeError("Samples must be triples of finite numbers in [-1, 1]");
      if (row[2] !== 0) dimensions = 3;
      else if (row[1] !== 0 && dimensions !== 3) dimensions = 2;
      return { x: row[0], y: row[1], z: row[2] };
    });
    const existing = catalogue.find(item => item.name === p.name);
    if (existing) {
      if (existing.description !== p.description || existing.periodPips !== p.period_pips ||
          samples.some((value, pip) => {
            const expected = module.sample(p.name as string, pip);
            return value.x !== expected.x || value.y !== expected.y || value.z !== expected.z;
          })) throw new TypeError("Cannot override default pattern: " + p.name);
    } else info.push(Object.freeze({name: p.name, description: p.description, periodPips: p.period_pips, dimensions}));
    return {name: p.name, description: p.description, samples};
  });
  const temporaries: NativePattern[] = [];
  let library: NativeLibrary;
  try {
    for (const p of checked) {
      const offsets = new module.OffsetVector();
      try {
        for (const v of p.samples) offsets.push_back(v);
        temporaries.push(new module.SampledPattern(p.name, p.description, offsets));
      } finally { offsets.delete(); }
    }
    // C++ takes owning copies before the temporary handles are released.
    library = new module.PatternLibrary(temporaries);
  } finally {
    for (const p of temporaries) p.delete();
  }
  const metadata = Object.freeze(info.map(p => Object.freeze({...p})));
  let disposed = false;
  return Object.freeze({
    sample(name: string, pipCount: number): Offset3 {
      if (disposed) throw new Error("Pattern library has been disposed");
      if (typeof name !== "string" || !names.has(name)) throw new Error("Unknown pattern name");
      validatePip(pipCount);
      return library.sample(name, pipCount);
    },
    catalogue(): readonly PatternInfo[] { return metadata; },
    dispose(): void {
      if (!disposed) { disposed = true; library.delete(); }
    }
  });
}
