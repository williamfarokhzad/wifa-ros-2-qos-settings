import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
// On a separate machine: npm install --no-save sharp
const sharp = require(process.env.WIFA_SHARP_PATH || 'sharp');
for (const name of ['reliability-matrix','late-join-cache']) {
  const svg = fileURLToPath(new URL(name + '.svg', import.meta.url));
  for (const [suffix, width] of [['',760],['-380',380]]) {
    const out = fileURLToPath(new URL(name + suffix + '.webp', import.meta.url));
    await sharp(svg).resize({width}).webp({quality:88,effort:6}).toFile(out);
  }
}
