import { test, expect } from '@playwright/test';

test('publishing page surfaces workflow controls', async ({ page }) => {
  await page.goto('/publishing');
  await expect(page.getByRole('heading', { name: 'Publishing', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Run Publishing/i })).toBeVisible();
  await expect(page.locator('table').first()).toBeVisible();
});
