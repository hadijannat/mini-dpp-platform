import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const frontendDir = path.resolve(__dirname, '../..');
const distIndex = path.join(frontendDir, 'dist', 'index.html');
const sourceIndex = path.join(frontendDir, 'index.html');

function loadIndexHtml(): string {
  const sourceStat = fs.existsSync(sourceIndex) ? fs.statSync(sourceIndex) : null;
  const distStat = fs.existsSync(distIndex) ? fs.statSync(distIndex) : null;
  const target =
    distStat && sourceStat && distStat.mtimeMs >= sourceStat.mtimeMs
      ? distIndex
      : sourceIndex;
  return fs.readFileSync(target, 'utf8');
}

describe('index.html SEO metadata', () => {
  it('contains updated title and JSON-LD blocks', () => {
    const html = loadIndexHtml();

    expect(html).toContain('Mini DPP Platform | Digital Product Passport (ESPR) | AAS + DPP4.0');
    expect(html).toContain('"@type":"SoftwareApplication"');
    expect(html).toContain('"@type":"Organization"');
    expect(html).toContain('"@type":"FAQPage"');
  });
});
