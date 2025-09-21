import { test, expect } from '@playwright/test';

test('topics table renders rows from Supabase', async ({ page }) => {
  await page.goto('/topics');
  await expect(page.getByRole('heading', { name: 'Topics' })).toBeVisible();
  const firstRow = page.locator('tbody tr').first();
  await expect(firstRow).toBeVisible();
  await expect(firstRow).toContainText(/AI|Topic/);
});
