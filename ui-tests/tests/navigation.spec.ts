import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

const NAV_ITEMS = [
  'Dashboard', 'Episodes', 'Digests', 'Feeds', 'Topics', 'Watch Themes',
  'Recurring Topics', 'Story Arcs', 'Script Lab', 'Publishing', 'Logs',
  'Maintenance', 'Settings',
];

test('navigation links visible on desktop', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/dashboard');
  const nav = page.locator('nav, aside').first();
  for (const item of NAV_ITEMS) {
    await expect(nav.getByRole('link', { name: item, exact: true })).toBeVisible();
  }
});
