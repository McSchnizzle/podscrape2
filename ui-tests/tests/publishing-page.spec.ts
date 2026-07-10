import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('publishing page surfaces workflow controls', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/publishing');
  await expect(page.getByRole('heading', { name: 'Publishing', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Run Publishing/i })).toBeVisible();
  await expect(page.locator('table').first()).toBeVisible();
});
