// preload-require.cjs — inject require into the global scope for ESM bundles
// that use dynamic require() internally.
// Usage: node --require ./preload-require.cjs render.js ...
// (CJS files loaded via --require run before ESM modules, so globalThis.require
//  is available when the Bun-bundled @hyperframes/producer initialises.)
const { createRequire } = require('module');
globalThis.require = createRequire(require.resolve('./package.json'));
