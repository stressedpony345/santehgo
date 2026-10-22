import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000';
const localPython = process.platform === 'win32'
  ? join(process.cwd(), '.venv-e2e', 'Scripts', 'python.exe')
  : join(process.cwd(), '.venv-e2e', 'bin', 'python');
const pythonExecutable = JSON.stringify(
  process.env.E2E_PYTHON || (existsSync(localPython) ? localPython : process.platform === 'win32' ? 'python' : 'python3'),
);

export default defineConfig({
  testDir: './tests/e2e/specs',
  outputDir: './test-results',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : 4,
  timeout: 30_000,
  expect: {
    timeout: 7_000,
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.001,
      stylePath: './tests/e2e/visual.css',
    },
  },
  reporter: process.env.CI
    ? [['line'], ['html', { outputFolder: 'playwright-report', open: 'never' }]]
    : [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  snapshotPathTemplate: '{testDir}/../snapshots/{projectName}/{testFilePath}/{arg}{ext}',
  use: {
    baseURL,
    locale: 'ru-RU',
    timezoneId: 'Asia/Yekaterinburg',
    reducedMotion: 'reduce',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: `${pythonExecutable} scripts/e2e_server.py`,
        url: baseURL,
        reuseExistingServer: process.env.PW_REUSE_SERVER === '1',
        timeout: 120_000,
        stdout: 'pipe',
        stderr: 'pipe',
      },
  projects: [
    {
      name: 'desktop-chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: 'desktop-firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1366, height: 900 },
      },
    },
    {
      name: 'mobile-chromium',
      use: {
        ...devices['Pixel 7'],
      },
    },
    {
      name: 'mobile-webkit',
      use: {
        ...devices['iPhone 13'],
      },
    },
  ],
});
