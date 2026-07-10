import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('settings page loads', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(page.locator('text=Content Filtering').first()).toBeVisible();
});
