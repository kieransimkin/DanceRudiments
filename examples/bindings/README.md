# Runnable binding examples

By [Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).

Run the commands in the [root README](https://github.com/kieransimkin/DanceRudiments#language-bindings).
All paths there are relative to the repository root. `cpp` uses an installed
CMake package; `python` imports the actual extension; `javascript/node.mjs`
loads the production Emscripten module. `typescript` is a small browser consumer,
not the self-contained visualizer: build the wrapper and Emscripten output,
compile its `tsconfig.json`, serve the repository root, then open
`examples/bindings/typescript/`.

The browser sample uses an import map to keep this example dependency-light.
With a bundler, provide an equivalent mapping and ensure the `.wasm` binary is
served at the URL resolved by the factory (or supply `locateFile`). Never bind
the visualizer's snapshot WASM to the production wrapper: the interfaces differ.
`typescript/wasm.d.ts` supplies a local type declaration for the loader subpath;
it does not implement or replace any runtime movement.

`pulse.score.json` compiles to a one-beat private pattern called `tutorial_pulse`.
It is not added to the default catalogue. C++ and Python also demonstrate a
four-**pip** table solely to show the storage/ownership API, not as a dance phrase.
