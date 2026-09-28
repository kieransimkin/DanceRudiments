export type Offset3 = Readonly<{ x: number; y: number; z: number }>;
export type RudimentName = "bounce" | "sway" | "circle" | "figure_eight" | "step_touch" | "box_step" | "helix" | "clay_background" | "single_stroke_roll" | "double_stroke_roll" | "multiple_bounce_roll" | "single_paradiddle" | "flam" | "drag" | "five_stroke_roll";
export type RudimentInfo = Readonly<{ name: RudimentName; description: string; periodPips: 64 | 128 | 256; dimensions: 1 | 2 | 3 }>;
type NativeModule = { sample(name: string, pipCount: number): Offset3 };

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
  { name: "five_stroke_roll", description: "Two diddles resolving to an accented fifth motion", periodPips: 128, dimensions: 2 }
];

let native: NativeModule | undefined;
export function bindNative(module: NativeModule): void { native = module; }
export function sample(name: RudimentName, pipCount: number): Offset3 {
  if (!native) throw new Error("DanceRudiments WASM is not bound. Call bindNative(await createDanceRudiments()).");
  if (!Number.isInteger(pipCount)) throw new TypeError("pipCount must be an integer");
  return native.sample(name, pipCount);
}
