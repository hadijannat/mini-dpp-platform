import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');
const distIndexPath = path.resolve(frontendDir, 'dist/index.html');
const viteBin = path.resolve(frontendDir, 'node_modules/vite/bin/vite.js');
const previewHost = '127.0.0.1';
const previewPort = Number(process.env.PRERENDER_PORT ?? 4173);
const previewUrl = `http://${previewHost}:${previewPort}/`;
const skipPrerender = process.env.SKIP_LANDING_PRERENDER === '1';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, retries = 80, intervalMs = 250) {
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await fetch(url, { method: 'GET' });
      if (response.ok) {
        return;
      }
    } catch {
      // Preview server not ready yet.
    }
    await sleep(intervalMs);
  }
  throw new Error(`Preview server did not become ready at ${url}`);
}

function startPreviewServer() {
  const child = spawn(process.execPath, [viteBin, 'preview', '--host', previewHost, '--port', String(previewPort), '--strictPort'], {
    cwd: frontendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: process.env,
  });

  child.stdout.on('data', (chunk) => {
    process.stdout.write(`[prerender] ${chunk}`);
  });
  child.stderr.on('data', (chunk) => {
    process.stderr.write(`[prerender] ${chunk}`);
  });

  return child;
}

async function prerenderLanding() {
  if (skipPrerender) {
    console.log('[prerender] SKIP_LANDING_PRERENDER=1 set; skipping prerender step.');
    return;
  }

  const preview = startPreviewServer();
  let browser;

  try {
    await waitForServer(previewUrl);

    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

    await page.route(/\/api\/v1\/public(?:\/[^/]+)?\/landing\/summary(?:\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tenant_slug: 'all',
          published_dpps: 12,
          active_product_families: 4,
          dpps_with_traceability: 7,
          latest_publish_at: '2026-02-10T12:00:00Z',
          generated_at: '2026-02-10T12:00:00Z',
          scope: 'all',
          refresh_sla_seconds: 30,
        }),
      });
    });

    await page.route(/\/api\/v1\/public\/landing\/regulatory-timeline(?:\?.*)?$/, async (route) => {
      const url = route.request().url();
      const track = new URL(url).searchParams.get('track');
      const allEvents = [
        {
          id: 'espr-entry-into-force',
          date: '2024-07-18',
          date_precision: 'day',
          track: 'regulation',
          title: 'ESPR entered into force',
          plain_summary:
            'Regulation (EU) 2024/1781 is now in force and starts the legal DPP rollout baseline.',
          audience_tags: ['brands', 'compliance-teams'],
          status: 'past',
          verified: true,
          verification: {
            checked_at: '2026-02-10T12:00:00Z',
            method: 'content-match',
            confidence: 'high',
          },
          sources: [
            {
              label: 'European Commission — ESPR',
              url: 'https://commission.europa.eu',
              publisher: 'European Commission',
              retrieved_at: '2026-02-10T12:00:00Z',
              sha256: 'a'.repeat(64),
            },
          ],
        },
        {
          id: 'cencenelec-cwa-workshop-launch',
          date: '2024-06-24',
          date_precision: 'day',
          track: 'standards',
          title: 'CEN workshop on DPP design guidelines launched',
          plain_summary:
            'A CEN workshop starts work on practical design guidelines for Digital Product Passports.',
          audience_tags: ['standards'],
          status: 'past',
          verified: true,
          verification: {
            checked_at: '2026-02-10T12:00:00Z',
            method: 'content-match',
            confidence: 'high',
          },
          sources: [
            {
              label: 'CEN-CENELEC Workshop Announcement',
              url: 'https://www.cencenelec.eu',
              publisher: 'CEN-CENELEC',
              retrieved_at: '2026-02-10T12:00:00Z',
              sha256: 'b'.repeat(64),
            },
          ],
        },
      ];
      const events =
        track === 'regulation'
          ? allEvents.filter((event) => event.track === 'regulation')
          : track === 'standards'
            ? allEvents.filter((event) => event.track === 'standards')
            : allEvents;

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          generated_at: '2026-02-10T12:00:00Z',
          fetched_at: '2026-02-10T12:00:00Z',
          source_status: 'fresh',
          refresh_sla_seconds: 82800,
          digest_sha256: 'c'.repeat(64),
          events,
        }),
      });
    });

    await page.goto(previewUrl, { waitUntil: 'networkidle' });
    await page.waitForSelector('h1');

    const renderedHtml = await page.content();
    if (!renderedHtml.includes('Ship passport experiences fast, with claims technical teams can verify')) {
      throw new Error('Prerender validation failed: hero heading not found in rendered HTML.');
    }
    if (!renderedHtml.includes('Evidence first, marketing second')) {
      throw new Error('Prerender validation failed: proof strip heading not found.');
    }
    if (!renderedHtml.includes('"@type":"SoftwareApplication"')) {
      throw new Error('Prerender validation failed: SoftwareApplication JSON-LD missing.');
    }
    if (!renderedHtml.includes('"@type":"Organization"')) {
      throw new Error('Prerender validation failed: Organization JSON-LD missing.');
    }
    if (!renderedHtml.includes('"@type":"FAQPage"')) {
      throw new Error('Prerender validation failed: FAQPage JSON-LD missing.');
    }
    if (!renderedHtml.includes('Regulatory timeline highlights')) {
      throw new Error('Prerender validation failed: timeline heading not found.');
    }
    if (!renderedHtml.includes('ESPR entered into force')) {
      throw new Error('Prerender validation failed: timeline event not found.');
    }

    const originalIndex = await readFile(distIndexPath, 'utf8');
    const doctypeMatch = originalIndex.match(/^<!doctype html>/i);
    const serialized = doctypeMatch ? `<!doctype html>\n${renderedHtml}` : renderedHtml;

    await writeFile(distIndexPath, serialized, 'utf8');
    console.log(`[prerender] Wrote prerendered landing page to ${distIndexPath}`);
  } finally {
    if (browser) {
      await browser.close();
    }

    preview.kill('SIGTERM');
    await new Promise((resolve) => {
      preview.once('exit', resolve);
      setTimeout(() => {
        preview.kill('SIGKILL');
        resolve();
      }, 5000);
    });
  }
}

prerenderLanding().catch((error) => {
  console.error('[prerender] Failed:', error);
  process.exitCode = 1;
});
