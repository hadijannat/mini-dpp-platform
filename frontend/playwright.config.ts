import { defineConfig } from '@playwright/test';
import fs from 'fs';
import os from 'os';
import path from 'path';

function resolveChromiumExecutable(): string | undefined {
  const cacheDir = path.join(os.homedir(), 'Library/Caches/ms-playwright');
  if (!fs.existsSync(cacheDir)) return undefined;

  const candidates = fs
    .readdirSync(cacheDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith('chromium_headless_shell-'))
    .map((entry) => entry.name);

  if (candidates.length === 0) return undefined;

  const latest = candidates.sort((a, b) => {
    const aVersion = Number(a.split('-').pop() || 0);
    const bVersion = Number(b.split('-').pop() || 0);
    return aVersion - bVersion;
  })[candidates.length - 1];

  const archFolder = os.arch() === 'arm64'
    ? 'chrome-headless-shell-mac-arm64'
    : 'chrome-headless-shell-mac-x64';
  const executable = path.join(cacheDir, latest, archFolder, 'chrome-headless-shell');
  return fs.existsSync(executable) ? executable : undefined;
}

const chromiumExecutable = resolveChromiumExecutable();

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    browserName: 'chromium',
    launchOptions: chromiumExecutable ? { executablePath: chromiumExecutable } : {},
  },
});
