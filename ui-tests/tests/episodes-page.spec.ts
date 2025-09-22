import { test, expect } from '@playwright/test';

test('episodes page loads', async ({ page }) => {
  await page.goto('/episodes');
  await expect(page.getByRole('heading', { name: 'Episodes' })).toBeVisible();
  await expect(page.locator('table')).toBeVisible();
});
