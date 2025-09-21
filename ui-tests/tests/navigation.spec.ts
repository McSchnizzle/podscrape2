import { test, expect } from '@playwright/test';

const NAV_ITEMS = ['Dashboard', 'Feeds', 'Topics', 'Script Lab', 'Episodes', 'Publishing', 'Maintenance', 'Settings'];

test('navigation links visible on desktop', async ({ page }) => {
  await page.goto('/dashboard');
  const nav = page.locator('nav');
  for (const item of NAV_ITEMS) {
    await expect(nav.getByRole('link', { name: item })).toBeVisible();
  }
});

