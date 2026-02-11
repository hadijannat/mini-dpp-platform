import { test, expect } from '@playwright/test';

const username = process.env.PLAYWRIGHT_USERNAME ?? 'publisher';
const password = process.env.PLAYWRIGHT_PASSWORD ?? 'publisher123';

async function ensureSignedIn(page: import('@playwright/test').Page) {
  await page.goto('/console/dpps');

  const signInButton = page.getByRole('button', { name: /sign in with keycloak/i });
  const needsLogin = await signInButton.isVisible({ timeout: 5000 }).catch(() => false);

  if (!needsLogin) {
    await page.waitForURL(/\/console\//, { timeout: 60000 });
    return;
  }

  await signInButton.click();
  await page.waitForURL(/\/realms\/dpp-platform\/protocol\/openid-connect\/auth/);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('#kc-login');
  await page.waitForFunction(
    () => window.location.pathname.startsWith('/console'),
    { timeout: 60000 }
  );
}

test('publisher navigation and action buttons work', async ({ page }) => {
  await ensureSignedIn(page);

  await page.goto('/console/templates');
  await page.getByTestId('templates-refresh-all').click();
  await expect(page.locator('[data-testid^="template-card-"]').first()).toBeVisible({
    timeout: 60000,
  });

  await page.goto('/console/dpps');
  await page.getByTestId('dpp-create-open').click();
  await expect(page.getByTestId('dpp-create-modal')).toBeVisible();
  await page.locator('input[name="manufacturerPartId"]').fill(`pw-test-${Date.now()}`);
  await page.locator('input[name="serialNumber"]').fill('pw-serial-001');
  const templateCheckboxes = page.locator('input[type="checkbox"]');
  if (await templateCheckboxes.count()) {
    await templateCheckboxes.first().check();
  }
  await page.getByTestId('dpp-create-submit').click();
  await expect(page.getByTestId('dpp-create-modal')).toBeHidden({ timeout: 20000 });

  const viewLink = page.locator('[data-testid^="dpp-view-"]').first();
  await expect(viewLink).toBeVisible();
  await viewLink.click();
  await expect(page).toHaveURL(/\/dpp\/[0-9a-f-]+/);
  await expect(page.getByTestId('viewer-back')).toBeVisible();
  await page.getByTestId('viewer-back').click();
  await expect(page).toHaveURL(/\/console\/dpps/);

  const editLink = page.locator('[data-testid^="dpp-edit-"]').first();
  await editLink.click();
  await expect(page).toHaveURL(/\/console\/dpps\/[0-9a-f-]+/);
  await expect(page.getByRole('heading', { name: /submodels/i })).toBeVisible();
  await expect(page.getByTestId('dpp-refresh-rebuild')).toBeVisible();
  await page.getByTestId('dpp-refresh-rebuild').click();
  await expect(page.getByTestId('dpp-refresh-rebuild')).not.toBeDisabled({ timeout: 60000 });
  const partialFailure = page.getByText(/Refresh & Rebuild partially failed for templates:/i);
  const partialFailureVisible = await partialFailure.isVisible({ timeout: 2000 }).catch(() => false);
  if (partialFailureVisible) {
    await expect(partialFailure).toContainText(/templates:/i);
  }

  const submodelEdit = page.locator('[data-testid^="submodel-edit-"]').first();
  if (await submodelEdit.count()) {
    await submodelEdit.click();
  } else {
    await page.locator('[data-testid^="submodel-add-"]').first().click();
  }

  await expect(page.getByRole('heading', { name: /edit submodel/i })).toBeVisible();
  await page.getByTestId('submodel-back').click();
  await expect(page).toHaveURL(/\/console\/dpps\/[0-9a-f-]+/);

  await page.getByTestId('dpp-back').click();
  await expect(page).toHaveURL(/\/console\/dpps/);
});
