const PI = Math.PI;
export const wrapPip = (pip, period) => ((pip % period) + period) % period;
const phase = (pip, period) => wrapPip(pip, period) / period;
const smooth = t => t * t * (3 - 2 * t);
const lerp = (a, b, t) => a + (b - a) * smooth(t);

const clayKeys = [
  [0,0,0],[23,2/14,-.1],[33,13/14,-.8],[49,5/14,-.4],[87,-3/14,.2],
  [100,-1,.9],[118,-5/14,.5],[154,1/14,0],[169,12/14,1],[187,4/14,.5],
  [215,-2/14,-.2],[228,-10/14,-.9],[243,-3/14,-.3],[256,0,0]
];
const clayTable = Array.from({length: 256}, (_, pip) => {
  let i = 0;
  while (i + 1 < clayKeys.length && pip > clayKeys[i + 1][0]) i++;
  const a = clayKeys[i], b = clayKeys[i + 1], t = (pip - a[0]) / (b[0] - a[0]);
  return {x: lerp(a[1], b[1], t), y: lerp(a[2], b[2], t), z: 0};
});

const strokeMotion = (pip, period, strokes) => {
  let x = 0, y = 0;
  for (const [start, hand, strength, width] of strokes) {
    const distance = wrapPip(pip - start, period);
    if (distance >= width) continue;
    const s = Math.sin(PI * distance / width);
    const amount = strength * s * s;
    x += hand * amount; y -= amount * .72;
  }
  return {x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y)), z: 0};
};
const alternating = [[0,1,.92,8],[8,-1,.92,8],[16,1,.92,8],[24,-1,.92,8],[32,1,.92,8],[40,-1,.92,8],[48,1,.92,8],[56,-1,.92,8]];
const doubles = [[0,1,.88,8],[8,1,.72,8],[16,-1,.88,8],[24,-1,.72,8],[32,1,.88,8],[40,1,.72,8],[48,-1,.88,8],[56,-1,.72,8]];
const paradiddle = [[0,1,1,8],[8,-1,.72,8],[16,1,.72,8],[24,1,.72,8],[32,-1,1,8],[40,1,.72,8],[48,-1,.72,8],[56,-1,.72,8],
  [64,1,1,8],[72,-1,.72,8],[80,1,.72,8],[88,1,.72,8],[96,-1,1,8],[104,1,.72,8],[112,-1,.72,8],[120,-1,.72,8]];

export const catalogue = [
  ["bounce","One-beat vertical bounce",64,1],["sway","Two-beat side-to-side sway",128,1],
  ["circle","One-beat circular orbit",64,2],["figure_eight","Two-beat figure eight",128,2],
  ["step_touch","Two-beat side step with a small lift",128,2],["box_step","Four-beat softened square path",256,2],
  ["helix","Four-beat double-turn helix",256,3],["clay_background","Clay/Stars four-beat accented background drift",256,2],
  ["single_stroke_roll","Alternating R/L strokes with smooth attack and decay",64,2],
  ["double_stroke_roll","RRLL strokes with a softer second motion",64,2],
  ["multiple_bounce_roll","Decaying same-hand bounce clusters",64,2],
  ["single_paradiddle","RLRR LRLL with accented lead strokes",128,2],
  ["flam","Grace motion flowing into an opposite-hand primary motion",64,2],
  ["drag","Two grace motions flowing into an opposite-hand primary motion",64,2],
  ["five_stroke_roll","Two diddles resolving to an accented fifth motion",128,2]
].map(([name, description, periodPips, dimensions]) => ({name, description, periodPips, dimensions}));

export function sample(name, pip) {
  const p64 = phase(pip, 64), p128 = phase(pip, 128), p256 = phase(pip, 256);
  if (name === "bounce") return {x: 1 - 4 * Math.abs(p64 - .5), y:0, z:0};
  if (name === "sway") return {x: Math.sin(2*PI*p128), y:0, z:0};
  if (name === "circle") { const a=2*PI*p64-PI/2; return {x:Math.cos(a),y:Math.sin(a),z:0}; }
  if (name === "figure_eight") { const a=2*PI*p128; return {x:Math.sin(a),y:Math.sin(2*a),z:0}; }
  if (name === "step_touch") { const q=Math.floor(wrapPip(pip,128)/32),t=wrapPip(pip,32)/32,x0=[-1,0,1,0],x1=[0,1,0,-1]; return {x:lerp(x0[q],x1[q],t),y:-Math.sin(PI*t)*.35,z:0}; }
  if (name === "box_step") { const e=Math.floor(wrapPip(pip,256)/64),t=wrapPip(pip,64)/64,x0=[-1,1,1,-1],y0=[-1,-1,1,1],x1=[1,1,-1,-1],y1=[-1,1,1,-1]; return {x:lerp(x0[e],x1[e],t),y:lerp(y0[e],y1[e],t),z:0}; }
  if (name === "helix") { const a=4*PI*p256; return {x:Math.cos(a),y:Math.sin(a),z:Math.sin(2*PI*p256)}; }
  if (name === "clay_background") return {...clayTable[wrapPip(pip,256)]};
  if (name === "single_stroke_roll") return strokeMotion(pip,64,alternating);
  if (name === "double_stroke_roll") return strokeMotion(pip,64,doubles);
  if (name === "multiple_bounce_roll") return strokeMotion(pip,64,[[0,1,.92,6],[6,1,.68,6],[12,1,.48,6],[18,1,.32,6],[32,-1,.92,6],[38,-1,.68,6],[44,-1,.48,6],[50,-1,.32,6]]);
  if (name === "single_paradiddle") return strokeMotion(pip,128,paradiddle);
  if (name === "flam") return strokeMotion(pip,64,[[0,-1,.34,10],[5,1,.9,14],[32,1,.34,10],[37,-1,.9,14]]);
  if (name === "drag") return strokeMotion(pip,64,[[0,-1,.28,8],[5,-1,.32,8],[10,1,.88,14],[32,1,.28,8],[37,1,.32,8],[42,-1,.88,14]]);
  if (name === "five_stroke_roll") return strokeMotion(pip,128,[[0,1,.72,9],[8,1,.62,9],[16,-1,.72,9],[24,-1,.62,9],[36,1,1,14],[64,-1,.72,9],[72,-1,.62,9],[80,1,.72,9],[88,1,.62,9],[100,-1,1,14]]);
  throw new RangeError(`Unknown dance rudiment: ${name}`);
}
