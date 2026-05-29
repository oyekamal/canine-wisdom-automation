// render.js — CLI wrapper for @hyperframes/producer
//
// IMPORTANT: must be launched via the preload shim so that the Bun-bundled
// @hyperframes/producer can use dynamic require():
//   node --require ./preload-require.cjs render.js <args>
// or via:  npm run render -- <args>
//
// The HTML file must declare its own duration on the composition root:
//   <div data-composition-id="root" data-duration="3"> ... </div>
//
// Usage:
//   node --require ./preload-require.cjs render.js \
//     --template /path/to/overlay.html \
//     --output   /path/to/out.webm \
//     [--width 1080] [--height 1920] [--fps 30] [--quality draft|standard|high]

import { createRenderJob, executeRenderJob } from '@hyperframes/producer';
import { parseArgs } from 'node:util';
import { resolve, dirname, basename } from 'node:path';

const { values } = parseArgs({
  options: {
    template: { type: 'string' },
    output:   { type: 'string' },
    width:    { type: 'string', default: '1080' },
    height:   { type: 'string', default: '1920' },
    fps:      { type: 'string', default: '30' },
    quality:  { type: 'string', default: 'standard' },
  }
});

if (!values.template || !values.output) {
  console.error('Usage: node --require ./preload-require.cjs render.js --template <html_path> --output <webm_path> [--width 1080] [--height 1920] [--fps 30] [--quality draft|standard|high]');
  process.exit(1);
}

const templatePath = resolve(values.template);
const outputPath   = resolve(values.output);
const projectDir   = dirname(templatePath);
const entryFile    = basename(templatePath);

const job = createRenderJob({
  fps:       parseInt(values.fps),
  width:     parseInt(values.width),
  height:    parseInt(values.height),
  quality:   values.quality,
  format:    'webm',   // VP9 + yuva420p — true alpha channel
  entryFile,
});

await executeRenderJob(job, projectDir, outputPath, (progress) => {
  if (progress.percent !== undefined) {
    process.stderr.write(`\r${Math.round(progress.percent * 100)}%`);
  }
});

process.stderr.write('\n');
console.log('OK: ' + outputPath);
