import { test, expect, type APIRequestContext, type Browser, type Page } from '@playwright/test';

type RoleKey = 'owner' | 'shared' | 'admin';

const creds: Record<RoleKey, { username: string; password: string }> = {
  owner: {
    username: process.env.PLAYWRIGHT_OWNER_USERNAME ?? process.env.PLAYWRIGHT_USERNAME ?? 'publisher',
    password: process.env.PLAYWRIGHT_OWNER_PASSWORD ?? process.env.PLAYWRIGHT_PASSWORD ?? 'publisher123',
  },
  shared: {
    username: process.env.PLAYWRIGHT_SHARED_USERNAME ?? 'viewer',
    password: process.env.PLAYWRIGHT_SHARED_PASSWORD ?? 'viewer123',
  },
  admin: {
    username: process.env.PLAYWRIGHT_ADMIN_USERNAME ?? 'admin',
    password: process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'admin123',
  },
};

function decodeJwtPayload(token: string): Record<string, unknown> {
  const [, payload] = token.split('.');
  if (!payload) {
    throw new Error('Invalid JWT payload.');
  }
  return JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')) as Record<string, unknown>;
}

async function signIn(
  page: Page,
  role: RoleKey,
  options?: { requireConsole?: boolean },
): Promise<{ inConsole: boolean; currentPath: string }> {
  const requireConsole = options?.requireConsole ?? true;

  await page.goto('/login');
  const hasLoginForm = await page
    .locator('#username')
    .isVisible({ timeout: 5000 })
    .catch(() => false);

  if (!hasLoginForm) {
    await page.waitForURL(
      (url) =>
        url.pathname.includes('/realms/') ||
        url.pathname.startsWith('/console') ||
        url.pathname.startsWith('/welcome'),
      { timeout: 60000 },
    );
  }

  const keycloakLoginFormVisible = await page
    .locator('#username')
    .isVisible({ timeout: 5000 })
    .catch(() => false);

  if (keycloakLoginFormVisible) {
    await page.fill('#username', creds[role].username);
    await page.fill('#password', creds[role].password);
    await page.click('#kc-login');
  }

  await page.waitForURL(
    (url) => url.pathname.startsWith('/console') || url.pathname.startsWith('/welcome'),
    { timeout: 60000 },
  );

  const currentPath = new URL(page.url()).pathname;
  const inConsole = currentPath.startsWith('/console');

  if (requireConsole && !inConsole) {
    throw new Error(
      `User "${creds[role].username}" authenticated but cannot access publisher console (landed on ${currentPath}).`,
    );
  }

  return { inConsole, currentPath };
}

async function getAccessToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => {
    const stores: Storage[] = [window.localStorage, window.sessionStorage];
    for (const store of stores) {
      const oidcKey = Object.keys(store).find((key) => key.startsWith('oidc.user:'));
      if (!oidcKey) {
        continue;
      }
      try {
        const parsed = JSON.parse(store.getItem(oidcKey) ?? '{}');
        if (typeof parsed.access_token === 'string') {
          return parsed.access_token;
        }
      } catch {
        // Continue scanning remaining storages/keys.
      }
    }
    return '';
  });
  if (!token) {
    throw new Error('Unable to extract OIDC access token from browser storage.');
  }
  return token;
}

async function ensureSharedPublisherRole(
  browser: Browser,
): Promise<string> {
  const sharedContext = await browser.newContext();
  const sharedPage = await sharedContext.newPage();
  await signIn(sharedPage, 'shared', { requireConsole: false });
  const sharedToken = await getAccessToken(sharedPage);
  const sharedPayload = decodeJwtPayload(sharedToken);
  const sharedSubject = String(sharedPayload.sub ?? '');

  if (!sharedSubject) {
    await sharedContext.close();
    throw new Error('Shared user token is missing a subject claim.');
  }
  await sharedContext.close();
  return sharedSubject;
}

async function grantReadShare(
  request: APIRequestContext,
  ownerToken: string,
  dppId: string,
  sharedUserSubject: string,
) {
  const tenantSlug = process.env.PLAYWRIGHT_TENANT_SLUG ?? 'default';
  const shareResp = await request.post(
    `/api/v1/tenants/${tenantSlug}/shares/dpp/${dppId}`,
    {
      headers: {
        Authorization: `Bearer ${ownerToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        user_subject: sharedUserSubject,
        permission: 'read',
      },
    },
  );

  if (!shareResp.ok()) {
    const body = await shareResp.text();
    throw new Error(`Failed to grant DPP share (${shareResp.status()}): ${body}`);
  }
}

async function createDpp(page: Page): Promise<string> {
  await page.goto('/console/templates');
  const refreshAll = page.getByTestId('templates-refresh-all');
  await expect(refreshAll).toBeVisible({ timeout: 60000 });
  await refreshAll.click();
  await expect(page.locator('[data-testid^="template-card-"]').first()).toBeVisible({
    timeout: 60000,
  });

  await page.goto('/console/dpps');
  await page.getByTestId('dpp-create-open').click();
  const createModal = page.getByTestId('dpp-create-modal');
  await expect(createModal).toBeVisible();

  const uniqueId = `matrix-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await page.locator('input[name="manufacturerPartId"]').fill(uniqueId);
  await page.locator('input[name="serialNumber"]').fill('matrix-001');

  const templateCheckboxes = createModal.locator('input[type="checkbox"]');
  if (await templateCheckboxes.count()) {
    await templateCheckboxes.first().check();
  }

  await page.getByTestId('dpp-create-submit').click();
  await expect(createModal).toBeHidden({ timeout: 20000 });

  const editLink = page.locator('[data-testid^="dpp-edit-"]').first();
  await expect(editLink).toBeVisible();
  const href = await editLink.getAttribute('href');
  await editLink.click();
  await expect(page).toHaveURL(/\/console\/dpps\//);

  const url = href ?? page.url();
  const parts = url.split('/');
  return parts[parts.length - 1];
}

async function assertDraftOwnerGating(page: Page) {
  await expect(page.getByTestId('dpp-refresh-rebuild')).toBeEnabled();
  await expect(page.getByRole('button', { name: /publish/i })).toBeEnabled();
  await expect(page.getByRole('button', { name: /capture event/i })).toBeEnabled();
}

async function assertReadOnlyGating(page: Page) {
  await expect(page.getByTestId('dpp-refresh-rebuild')).toBeDisabled();
  await expect(page.getByRole('button', { name: /publish/i })).toBeDisabled();
  await expect(page.getByRole('button', { name: /capture event/i })).toBeDisabled();
}

test.describe('Submodel Matrix', () => {
  test('owner full create->edit->rebuild->publish->viewer flow', async ({ page }) => {
    await signIn(page, 'owner');
    const dppId = await createDpp(page);

    await assertDraftOwnerGating(page);

    const submodelEdit = page.locator('[data-testid^="submodel-edit-"]').first();
    if (await submodelEdit.count()) {
      await submodelEdit.click();
    } else {
      await page.locator('[data-testid^="submodel-add-"]').first().click();
    }

    await expect(page).toHaveURL(/\/console\/dpps\/[0-9a-f-]+\/edit\//, { timeout: 30000 });
    await expect(page.getByRole('heading', { name: /edit submodel/i })).toBeVisible({ timeout: 30000 });
    await page.getByTestId('submodel-back').click();
    await expect(page).toHaveURL(new RegExp(`/console/dpps/${dppId}$`));

    await page.getByTestId('dpp-refresh-rebuild').click();
    await expect(page.getByTestId('dpp-refresh-rebuild')).not.toBeDisabled({ timeout: 60000 });

    await page.getByRole('button', { name: /publish/i }).click();
    await expect(page.getByText(/status/i)).toBeVisible();

    await page.goto(`/t/default/dpp/${dppId}`);
    await expect(page.getByText(/Product Information/i)).toBeVisible({ timeout: 30000 });
  });

  test('shared and admin matrix for button gating', async ({ page, browser, request }) => {
    const sharedSubject = await ensureSharedPublisherRole(browser);

    await signIn(page, 'owner');
    const ownerToken = await getAccessToken(page);
    const dppId = await createDpp(page);
    await grantReadShare(request, ownerToken, dppId, sharedSubject);

    const sharedContext = await browser.newContext();
    const sharedPage = await sharedContext.newPage();
    await signIn(sharedPage, 'shared', { requireConsole: false });
    await sharedPage.goto(`/console/dpps/${dppId}`);
    await expect(sharedPage).toHaveURL(new RegExp(`/console/dpps/${dppId}$`));
    await expect(sharedPage.getByText('Submodels', { exact: true })).toBeVisible();
    await assertReadOnlyGating(sharedPage);
    await sharedContext.close();

    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await signIn(adminPage, 'admin');
    await adminPage.goto(`/console/dpps/${dppId}`);
    await expect(adminPage.getByTestId('dpp-refresh-rebuild')).toBeEnabled();
    await expect(adminPage.getByRole('button', { name: /publish/i })).toBeEnabled();
    await adminContext.close();
  });

  test.describe('mobile viewport', () => {
    test.use({ viewport: { width: 390, height: 844 } });

    test('owner critical journey is operable on mobile', async ({ page }) => {
      await signIn(page, 'owner');
      const dppId = await createDpp(page);

      await expect(page.getByTestId('dpp-refresh-rebuild')).toBeVisible();
      await expect(page.getByRole('button', { name: /publish/i })).toBeVisible();

      await page.goto(`/console/dpps/${dppId}`);
      await page.getByRole('button', { name: /export/i }).click();
      await expect(page.getByRole('menuitem', { name: 'Export JSON', exact: true })).toBeVisible();
    });
  });
});
