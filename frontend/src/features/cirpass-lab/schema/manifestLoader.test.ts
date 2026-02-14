import { describe, expect, test } from 'vitest';
import { parseCirpassLabManifest } from './manifestLoader';

describe('manifestLoader normalization', () => {
  test('maps legacy ui_action to interaction block', () => {
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
          id: 'legacy-story',
          title: 'Legacy story',
          summary: 'Legacy payload',
          personas: ['Manufacturer'],
          references: [],
          steps: [
            {
              id: 'legacy-step',
              level: 'create',
              title: 'Legacy step',
              actor: 'Manufacturer',
              intent: 'Legacy intent',
              explanation_md: 'Legacy explanation',
              ui_action: {
                label: 'Legacy Continue',
                kind: 'form',
              },
              variants: ['happy'],
              checks: [],
            },
          ],
        },
      ],
    });

    expect(manifest.stories[0].steps[0].interaction?.kind).toBe('form');
    expect(manifest.stories[0].steps[0].interaction?.submit_label).toBe('Legacy Continue');
  });
});

