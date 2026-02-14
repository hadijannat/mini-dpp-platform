import { expect, test, type Page } from '@playwright/test';

type StoryStatus = 'fresh' | 'stale';

const manifestFixture = {
  manifest_version: 'v1.0.0',
  story_version: 'V3.1',
  generated_at: '2026-02-14T09:00:00Z',
  source_status: 'fresh',
  feature_flags: {
    scenario_engine_enabled: true,
    live_mode_enabled: true,
    inspector_enabled: true,
  },
  stories: [
    {
      id: 'core-loop-v3_1',
      title: 'CIRPASS Core Lifecycle Loop',
      summary: 'Lifecycle journey.',
      personas: ['Manufacturer', 'Authority', 'Repairer', 'Recycler'],
      learning_goals: ['Issue', 'Access', 'Update', 'Transfer', 'Deactivate'],
      references: [],
      version: 'V3.1',
      steps: [
        {
          id: 'create-passport',
          level: 'create',
          title: 'Create passport',
          actor: 'Manufacturer',
          intent: 'Create DPP payload.',
          explanation_md: 'Create fields are mandatory.',
          variants: ['happy'],
          api: {
            method: 'POST',
            path: '/api/v1/public/cirpass/stories/latest',
            auth: 'none',
            expected_status: 200,
          },
          checks: [],
        },
        {
          id: 'access-routing',
          level: 'access',
          title: 'Access routing',
          actor: 'Authority',
          intent: 'Route access by role.',
          explanation_md: 'Unauthorized should be denied.',
          variants: ['happy', 'unauthorized', 'not_found'],
          api: {
            method: 'GET',
            path: '/api/v1/public/dpps/{id}',
            auth: 'none',
            expected_status: 200,
          },
          checks: [],
        },
        {
          id: 'update-repair-chain',
          level: 'update',
          title: 'Update repair chain',
          actor: 'Repairer',
          intent: 'Append repair event.',
          explanation_md: 'Hash chain must remain valid.',
          variants: ['happy'],
          checks: [],
        },
        {
          id: 'transfer-handoff',
          level: 'transfer',
          title: 'Transfer handoff',
          actor: 'Retailer',
          intent: 'Transfer ownership.',
          explanation_md: 'Confidentiality maintained.',
          variants: ['happy'],
          checks: [],
        },
        {
          id: 'deactivate-loop',
          level: 'deactivate',
          title: 'Deactivate loop',
          actor: 'Recycler',
          intent: 'Mark end of life.',
          explanation_md: 'Recovered materials required.',
          variants: ['happy'],
          checks: [],
        },
      ],
    },
  ],
};

async function mockCirpassApis(page: Page, status: StoryStatus = 'fresh') {
  let submitted = false;

  await page.route(/\/api\/v1\/public\/cirpass\/stories\/latest(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        version: 'V3.1',
        release_date: '2025-12-19',
        source_url: 'https://cirpassproject.eu/project-results/',
        zenodo_record_url: 'https://zenodo.org/records/17979585',
        source_status: status,
        generated_at: '2026-02-14T09:00:00Z',
        fetched_at: '2026-02-14T08:30:00Z',
        levels: [
          {
            level: 'create',
            label: 'CREATE',
            objective: 'Build payload',
            stories: [{ id: 's1', title: 'Create', summary: 'Create the passport.' }],
          },
          {
            level: 'access',
            label: 'ACCESS',
            objective: 'Role views',
            stories: [{ id: 's2', title: 'Access', summary: 'Route role access.' }],
          },
          {
            level: 'update',
            label: 'UPDATE',
            objective: 'Repair events',
            stories: [{ id: 's3', title: 'Update', summary: 'Append repair event.' }],
          },
          {
            level: 'transfer',
            label: 'TRANSFER',
            objective: 'Ownership transfer',
            stories: [{ id: 's4', title: 'Transfer', summary: 'Transfer ownership.' }],
          },
          {
            level: 'deactivate',
            label: 'DEACTIVATE',
            objective: 'End of life',
            stories: [{ id: 's5', title: 'Deactivate', summary: 'Close lifecycle.' }],
          },
        ],
      }),
    });
  });

  await page.route(/\/api\/v1\/public\/cirpass\/lab\/manifest\/latest$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(manifestFixture),
    });
  });

  await page.route(/\/api\/v1\/public\/cirpass\/lab\/events$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        accepted: true,
        event_id: 'evt_123',
        stored_at: '2026-02-14T09:01:00Z',
      }),
    });
  });

  await page.route(/\/api\/v1\/public\/cirpass\/session(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_token: 'signed-session-token',
        expires_at: '2026-02-15T09:00:00Z',
      }),
    });
  });

  await page.route(/\/api\/v1\/public\/cirpass\/leaderboard\?.*$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        version: 'V3.1',
        entries: submitted
          ? [
              {
                rank: 1,
                nickname: 'tester_01',
                score: 980,
                completion_seconds: 120,
                version: 'V3.1',
                created_at: '2026-02-14T09:10:00Z',
              },
            ]
          : [],
      }),
    });
  });

  await page.route(/\/api\/v1\/public\/cirpass\/leaderboard\/submit$/, async (route) => {
    submitted = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        accepted: true,
        rank: 1,
        best_score: 980,
        version: 'V3.1',
      }),
    });
  });
}

test('landing teaser links to CIRPASS lab', async ({ page }) => {
  await mockCirpassApis(page);
  await page.goto('/');

  const teaser = page.getByRole('heading', { name: 'LoopForge: CIRPASS Twin-Layer Lab' });
  await teaser.scrollIntoViewIfNeeded();
  await expect(teaser).toBeVisible();

  await page.getByTestId('cirpass-teaser-primary').click();
  await expect(page).toHaveURL(/\/cirpass-lab/);
  await expect(page.getByTestId('cirpass-lab-page')).toBeVisible();

  await page.getByTestId('cirpass-back-home').click();
  await expect(page).toHaveURL(/\/$/);
});

test('deep link opens exact step and unauthorized variant explanation', async ({ page }) => {
  await mockCirpassApis(page);
  await page.goto('/cirpass-lab/story/core-loop-v3_1/step/access-routing?mode=mock&variant=unauthorized');

  await expect(page.getByTestId('cirpass-current-level')).toHaveText(/ACCESS/i);
  await expect(page.getByTestId('cirpass-variant-guidance')).toContainText('Unauthorized variant active');
  await expect(page.getByTestId('cirpass-mode-select')).toHaveValue('mock');
  await expect(page.getByTestId('cirpass-variant-select')).toHaveValue('unauthorized');
});

test('complete full 5-level simulator and submit leaderboard score', async ({ page }) => {
  await mockCirpassApis(page);
  await page.goto('/cirpass-lab');

  await page.getByTestId('cirpass-create-identifier').fill('did:web:dpp.eu:product:bike-2000');
  await page.getByTestId('cirpass-create-material').fill('Recycled aluminum + lithium battery pack');
  await page.getByTestId('cirpass-create-carbon').fill('14.2');
  await page.getByTestId('cirpass-level-submit').click();

  await expect(page.getByTestId('cirpass-current-level')).toHaveText(/ACCESS/i);

  await page.getByTestId('cirpass-access-consumer').check();
  await page.getByTestId('cirpass-access-authority').check();
  await page.getByTestId('cirpass-access-restricted').check();
  await page.getByTestId('cirpass-level-submit').click();

  await expect(page.getByTestId('cirpass-current-level')).toHaveText(/UPDATE/i);

  await page.getByTestId('cirpass-update-prev-hash').fill('prevhash-abcdef01');
  await page.getByTestId('cirpass-update-new-hash').fill('newhash-fedcba10');
  await page
    .getByTestId('cirpass-update-repair-event')
    .fill('Independent repairer replaced worn battery module.');
  await page.getByTestId('cirpass-level-submit').click();

  await expect(page.getByTestId('cirpass-current-level')).toHaveText(/TRANSFER/i);

  await page.getByTestId('cirpass-transfer-from').fill('B2B Wholesaler');
  await page.getByTestId('cirpass-transfer-to').fill('Second-hand Retailer');
  await page.getByTestId('cirpass-transfer-confidentiality').check();
  await page.getByTestId('cirpass-level-submit').click();

  await expect(page.getByTestId('cirpass-current-level')).toHaveText(/DEACTIVATE/i);

  await page.getByTestId('cirpass-deactivate-status').selectOption('end_of_life');
  await page.getByTestId('cirpass-deactivate-materials').fill('lithium, copper, nickel');
  await page.getByTestId('cirpass-deactivate-spawn').check();
  await page.getByTestId('cirpass-level-submit').click();

  await expect(page.getByText('Circular loop complete')).toBeVisible();

  await page.getByTestId('cirpass-leaderboard-nickname').fill('tester_01');
  await page.getByTestId('cirpass-leaderboard-submit').click();

  await expect(page.getByTestId('cirpass-submit-success')).toBeVisible();
  await expect(page.getByTestId('cirpass-leaderboard-list')).toContainText('tester_01');

  await expect(page.getByTestId('cirpass-copy-step-link')).toBeVisible();
});

test('handles stale source banner and mobile overflow safety', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockCirpassApis(page, 'stale');

  await page.goto('/cirpass-lab');
  await expect(page.getByTestId('cirpass-source-stale')).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  });

  expect(hasHorizontalOverflow).toBeFalsy();
});
