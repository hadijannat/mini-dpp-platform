import { expect, test } from '@playwright/test';

const viewports = [
  { label: 'desktop', width: 1280, height: 800 },
  { label: 'tablet', width: 768, height: 1024 },
  { label: 'mobile', width: 390, height: 844 },
];

test.describe('Landing page', () => {
  for (const viewport of viewports) {
    test(`renders without horizontal overflow on ${viewport.label}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/');

      await expect(
        page.getByRole('heading', {
          name: /Digital Product Passport Platform for ESPR-ready product data/i,
        }),
      ).toBeVisible();

      const hasHorizontalOverflow = await page.evaluate(() => {
        const root = document.documentElement;
        return root.scrollWidth > root.clientWidth + 1;
      });

      expect(hasHorizontalOverflow).toBeFalsy();
    });
  }

  test('shows aggregate metrics only even when API payload contains blocked fields', async ({ page }) => {
    await page.route(/\/api\/v1\/public(?:\/[^/]+)?\/landing\/summary(?:\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tenant_slug: 'default',
          published_dpps: 12,
          active_product_families: 4,
          dpps_with_traceability: 7,
          latest_publish_at: '2026-02-09T12:00:00Z',
          generated_at: '2026-02-10T00:00:00Z',
          serialNumber: 'SN-LEAK',
          payload: { raw: true },
        }),
      });
    });

    await page.goto('/');

    await page
      .getByRole('heading', { name: /What is public vs what stays protected/i })
      .scrollIntoViewIfNeeded();
    const metricsSection = page.locator('#metrics');
    await metricsSection.scrollIntoViewIfNeeded();

    await expect(page.getByText('Published DPPs')).toBeVisible();
    await expect(metricsSection.getByText('SN-LEAK')).toHaveCount(0);
    await expect(metricsSection.getByText('serialNumber')).toHaveCount(0);
  });

  test('timeline shows verified badges, supports filters, and opens source details', async ({
    page,
  }) => {
    await page.route(/\/api\/v1\/public\/landing\/regulatory-timeline(?:\?.*)?$/, async (route) => {
      const track = new URL(route.request().url()).searchParams.get('track');
      const allEvents = [
        {
          id: 'espr-entry-into-force',
          date: '2024-07-18',
          date_precision: 'day',
          track: 'regulation',
          title: 'ESPR entered into force',
          plain_summary: 'Regulation baseline.',
          audience_tags: ['brands'],
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
          id: 'cencenelec-workshop',
          date: '2024-06-24',
          date_precision: 'day',
          track: 'standards',
          title: 'CEN workshop on DPP design guidelines launched',
          plain_summary: 'Standards workshop milestone.',
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
        {
          id: 'battery-passport',
          date: '2027-02-18',
          date_precision: 'day',
          track: 'regulation',
          title: 'Battery passport requirement begins',
          plain_summary: 'Upcoming battery milestone.',
          audience_tags: ['battery-manufacturers'],
          status: 'upcoming',
          verified: false,
          verification: {
            checked_at: '2026-02-10T12:00:00Z',
            method: 'source-hash',
            confidence: 'medium',
          },
          sources: [],
        },
        {
          id: 'dpp-registry-deadline',
          date: '2026-07-19',
          date_precision: 'day',
          track: 'regulation',
          title: 'DPP registry deadline',
          plain_summary: 'Registry infrastructure deadline.',
          audience_tags: ['authorities'],
          status: 'upcoming',
          verified: true,
          verification: {
            checked_at: '2026-02-10T12:00:00Z',
            method: 'content-match',
            confidence: 'high',
          },
          sources: [
            {
              label: 'EUR-Lex',
              url: 'https://eur-lex.europa.eu',
              publisher: 'EUR-Lex',
              retrieved_at: '2026-02-10T12:00:00Z',
              sha256: 'd'.repeat(64),
            },
          ],
        },
        {
          id: 'cwa-comment-close',
          date: '2025-03-19',
          date_precision: 'day',
          track: 'standards',
          title: 'Draft CWA comment period closes',
          plain_summary: 'Standards comment period close milestone.',
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
              label: 'CEN-CENELEC Draft CWA News',
              url: 'https://www.cencenelec.eu',
              publisher: 'CEN-CENELEC',
              retrieved_at: '2026-02-10T12:00:00Z',
              sha256: 'e'.repeat(64),
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

    await page.goto('/');

    await expect(page.getByRole('heading', { name: /Verified DPP Timeline/i })).toBeVisible();
    await expect(page.getByText('Live verified feed')).toBeVisible();
    await expect(page.getByTestId('timeline-axis-rail')).toBeVisible();
    await expect(page.getByTestId('timeline-now-marker')).toBeVisible();
    await expect(page.getByTestId('timeline-card-espr-entry-into-force')).toBeVisible();
    await expect(page.getByTestId('timeline-card-battery-passport')).toBeVisible();
    await expect(page.getByText('Verified (High)').first()).toBeVisible();
    await expect(page.getByText('Unverified').first()).toBeVisible();

    const scrollContainer = page.getByTestId('timeline-scroll-container');
    const beforeScrollLeft = await scrollContainer.evaluate((el) => el.scrollLeft);
    await page.getByTestId('timeline-scroll-right').click();
    await expect
      .poll(async () => scrollContainer.evaluate((el) => el.scrollLeft))
      .toBeGreaterThan(beforeScrollLeft);

    await page.getByRole('tab', { name: 'Standards' }).click();
    await expect(page.getByTestId('timeline-card-cencenelec-workshop')).toBeVisible();

    await page.getByTestId('timeline-card-cencenelec-workshop').click();
    await expect(page.getByText('Official citations')).toBeVisible();
    await expect(page.getByRole('link', { name: /CEN-CENELEC Workshop Announcement/i })).toBeVisible();
  });

  test('mobile menu reveals navigation and auth actions', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await page.getByRole('button', { name: /open menu/i }).click();

    await expect(page.getByRole('link', { name: /^Demo$/ })).toBeVisible();
    await expect(page.getByRole('link', { name: 'FAQ' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Standards' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible();
  });

  test('header anchor links reach deferred standards section', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Standards' }).click();
    await expect(page).toHaveURL(/#standards$/);
    await expect(page.getByRole('heading', { name: 'Capability claims with explicit evidence' })).toBeVisible();
  });

  test('faq section is present and reachable from header navigation', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'FAQ' }).click();
    await expect(page).toHaveURL(/#faq$/);
    await expect(
      page.getByRole('heading', { name: 'Common questions from compliance and engineering teams' }),
    ).toBeVisible();
  });

  test('hero CTAs navigate to sample section and quickstart link', async ({ page }) => {
    await page.goto('/');

    await page.getByTestId('landing-hero-primary-cta').click();
    await expect(page.getByRole('heading', { name: 'Sample Passport Flow' })).toBeVisible();

    const popupPromise = page.waitForEvent('popup');
    await page.getByTestId('landing-hero-secondary-cta').click();
    const popup = await popupPromise;
    await popup.waitForLoadState('domcontentloaded');
    expect(popup.url()).toContain('github.com/hadijannat/mini-dpp-platform');
    await popup.close();
  });

  test('includes software JSON-LD blocks in page source', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByRole('heading', {
        name: /Digital Product Passport Platform for ESPR-ready product data/i,
      }),
    ).toBeVisible();
    const html = await page.content();
    expect(html).toContain('"@type":"SoftwareApplication"');
    expect(html).toContain('"@type":"Organization"');
    expect(html).toContain('"@type":"FAQPage"');
  });

  test('uses dedicated OG image asset', async ({ page }) => {
    const response = await page.goto('/');
    const html = await response?.text();
    expect(html).toContain('og-dpp-platform-1200x630.png');
  });
});
