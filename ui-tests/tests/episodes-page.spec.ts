import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('episodes page loads', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/episodes');
  await expect(page.getByRole('heading', { name: 'Episodes' })).toBeVisible();
  await expect(page.locator('table')).toBeVisible();
});
