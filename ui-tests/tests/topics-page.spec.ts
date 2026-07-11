import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('topics table renders rows from Supabase', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/topics');
  await expect(page.getByRole('heading', { name: 'Topics' })).toBeVisible();
  const firstCard = page.locator('.card').first();
  await expect(firstCard).toBeVisible();
  await expect(firstCard).toContainText(/AI|Topic/);
});
