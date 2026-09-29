// Factory declaration for the currently untyped Emscripten package subpath.
// Music: https://kieransimkin.co.uk/my-songs/
declare module "@kieransimkin/dance-rudiments/wasm" {
  type NativeModule = Parameters<typeof import("@kieransimkin/dance-rudiments").bindNative>[0];
  export interface FactoryOptions {
    locateFile?: (path: string, prefix: string) => string;
    wasmBinary?: ArrayBuffer | Uint8Array;
  }
  export default function createDanceRudiments(options?: FactoryOptions): Promise<NativeModule>;
}
