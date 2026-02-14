import { describe, expect, test } from 'vitest';
import { parseCirpassLabManifest } from './manifestLoader';

describe('cirpass lab manifest schema', () => {
  test('parses valid manifest payload', () => {
    const manifest = parseCirpassLabManifest({
      manifest_version: 'v1.0.0',
      story_version: 'V3.1',
      generated_at: '2026-02-14T00:00:00Z',
      source_status: 'fresh',
      feature_flags: {
        scenario_engine_enabled: true,
        live_mode_enabled: false,
        inspector_enabled: true,
      },
      stories: [
        {
          id: 'core',
          title: 'Core story',
          summary: 'Summary',
          personas: ['Manufacturer'],
          learning_goals: ['goal'],
          references: [],
          steps: [
            {
              id: 'create',
              level: 'create',
              title: 'Create',
              actor: 'Manufacturer',
              intent: 'Create payload',
              explanation_md: 'Explain',
              variants: ['happy'],
              checks: [],
            },
          ],
        },
      ],
    });

    expect(manifest.stories).toHaveLength(1);
    expect(manifest.stories[0].steps[0].level).toBe('create');
  });

  test('rejects malformed manifest payload', () => {
    expect(() =>
      parseCirpassLabManifest({
        manifest_version: 'v1.0.0',
        story_version: 'V3.1',
        generated_at: '2026-02-14T00:00:00Z',
        source_status: 'fresh',
        feature_flags: {
          scenario_engine_enabled: true,
          live_mode_enabled: false,
          inspector_enabled: true,
        },
        stories: [
          {
            id: 'core',
            title: 'Core story',
            summary: 'Summary',
            personas: ['Manufacturer'],
            references: [],
            steps: [
              {
                id: 'create',
                level: 'create',
                title: 'Create',
                actor: 'Manufacturer',
                intent: 'Create payload',
                explanation_md: 'Explain',
                variants: ['invalid_variant'],
                checks: [],
              },
            ],
          },
        ],
      }),
    ).toThrow(/Invalid CIRPASS lab manifest payload/);
  });
});
