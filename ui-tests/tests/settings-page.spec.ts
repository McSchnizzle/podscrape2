import { test, expect } from '@playwright/test';

test('settings page loads', async ({ page }) => {
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(page.locator('text=Content Filtering')).toBeVisible();
});
