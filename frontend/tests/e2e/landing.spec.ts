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
          name: /Digital Product Passport publishing for cross-functional teams/i,
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
    await page.route('**/api/v1/public/**/landing/summary', async (route) => {
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

    await expect(page.getByTestId('landing-metrics-success')).toBeVisible();
    await expect(page.getByText('SN-LEAK')).toHaveCount(0);
    await expect(page.getByText('payload')).toHaveCount(0);
    await expect(page.getByText('Published DPPs')).toBeVisible();
  });

  test('mobile menu reveals navigation and auth actions', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await page.getByRole('button', { name: /open menu/i }).click();

    await expect(page.getByRole('link', { name: 'Audiences' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Workflow' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });
});
