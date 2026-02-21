import { useCallback, useMemo } from 'react';
import type { CirpassLabMode, CirpassLabVariant } from '../schema/storySchema';
import type { CirpassLevelKey } from '../machines/cirpassMachine';

const STORAGE_KEY = 'cirpass-lab-progress-v1';

export interface StoryProgressSnapshot {
  story_id: string;
  step_id: string;
  completed_levels: CirpassLevelKey[];
  mode: CirpassLabMode;
  variant: CirpassLabVariant;
  updated_at: number;
}

interface StoryProgressStore {
  stories: Record<string, StoryProgressSnapshot>;
}

const EMPTY_STORE: StoryProgressStore = { stories: {} };

function readStore(): StoryProgressStore {
  if (typeof window === 'undefined') {
    return EMPTY_STORE;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return EMPTY_STORE;
  }

  try {
    const parsed = JSON.parse(raw) as StoryProgressStore;
    if (!parsed || typeof parsed !== 'object' || typeof parsed.stories !== 'object') {
      return EMPTY_STORE;
    }
    return parsed;
  } catch {
    return EMPTY_STORE;
  }
}

function writeStore(store: StoryProgressStore): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function useStoryProgress(storyId: string) {
  const loadProgress = useCallback((): StoryProgressSnapshot | null => {
    if (!storyId.trim()) {
      return null;
    }
    const store = readStore();
    return store.stories[storyId] ?? null;
  }, [storyId]);

  const saveProgress = useCallback(
    (snapshot: Omit<StoryProgressSnapshot, 'updated_at' | 'story_id'>) => {
      if (!storyId.trim()) {
        return;
      }

      const store = readStore();
      store.stories[storyId] = {
        story_id: storyId,
        updated_at: Date.now(),
        ...snapshot,
      };
      writeStore(store);
    },
    [storyId],
  );

  const resetStory = useCallback(() => {
    if (!storyId.trim()) {
      return;
    }

    const store = readStore();
    delete store.stories[storyId];
    writeStore(store);
  }, [storyId]);

  const resetAll = useCallback(() => {
    writeStore(EMPTY_STORE);
  }, []);

  return useMemo(
    () => ({
      loadProgress,
      saveProgress,
      resetStory,
      resetAll,
    }),
    [loadProgress, resetAll, resetStory, saveProgress],
  );
}
