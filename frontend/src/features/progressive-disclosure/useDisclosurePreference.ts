import { useEffect, useState } from 'react';

function readStoredBoolean(key: string, fallback: boolean): boolean {
  if (typeof window === 'undefined') return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  return fallback;
}

export function useDisclosurePreference(
  key: string,
  fallback = false,
): [boolean, (value: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => readStoredBoolean(key, fallback));

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(key, String(value));
  }, [key, value]);

  return [value, setValue];
}
