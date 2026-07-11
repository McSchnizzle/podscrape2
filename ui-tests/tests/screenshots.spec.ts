import { test } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

/**
 * Visual capture for the kanban #2846 Phase 2 house-design-system redesign.
 * Not a pass/fail assertion suite -- these screenshots are what got looked
 * at (per the design quality-bar's "render it and look" rule) to sign off
 * the redesign in both the light ("Warm Cream / Forest") and dark
 * ("Dark Done Right") themes. Kept here so the capture is reproducible.
 */

const PAGES = ['/dashboard', '/episodes', '/feeds', '/watch-themes'];
const THEMES = ['light', 'dark'] as const;

async function setTheme(page: import('@playwright/test').Page, theme: 'light' | 'dark') {
  await page.evaluate((t) => {
    document.documentElement.setAttribute('data-theme', t);
    window.localStorage.setItem('podcast-admin-theme', t);
  }, theme);
}

test.describe('design screenshots', () => {
  test('login page (light + dark)', async ({ page }) => {
    test.skip(!process.env.ADMIN_PASSWORD, 'ADMIN_PASSWORD not set in the test environment');

    await page.goto('/login');
    await page.waitForTimeout(200);
    await page.screenshot({ path: 'screenshots/login-light.png', fullPage: true });

    await setTheme(page, 'dark');
    await page.reload();
    await page.waitForTimeout(200);
    await page.screenshot({ path: 'screenshots/login-dark.png', fullPage: true });
  });

  for (const theme of THEMES) {
    test(`admin pages (${theme})`, async ({ page }) => {
      await loginAsAdmin(page);
      await setTheme(page, theme);

      for (const path of PAGES) {
        await page.goto(path, { waitUntil: 'networkidle' });
        await page.waitForTimeout(300);
        const name = path.replace(/^\//, '');
        await page.screenshot({ path: `screenshots/${name}-${theme}.png`, fullPage: true });
      }
    });
  }
});
