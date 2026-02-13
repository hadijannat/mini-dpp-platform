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

    const metrics = page.getByTestId('landing-metrics-success');
    await expect(metrics).toBeVisible();
    await expect(metrics.getByText('SN-LEAK')).toHaveCount(0);
    await expect(page.getByText('Published DPPs')).toBeVisible();
  });

  test('mobile menu reveals navigation and auth actions', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await page.getByRole('button', { name: /open menu/i }).click();

    await expect(page.getByRole('link', { name: 'Demo' })).toBeVisible();
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
