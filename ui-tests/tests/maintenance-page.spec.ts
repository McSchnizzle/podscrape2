import { test, expect } from '@playwright/test';

test('maintenance page lists pipeline and activity sections', async ({ page }) => {
  await page.goto('/maintenance');
  await expect(page.getByRole('heading', { name: 'Maintenance' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Trigger Full Pipeline/i })).toBeVisible();
  await expect(page.locator('.card').filter({ hasText: 'Supabase Pipeline Runs' })).toBeVisible();
  await expect(page.locator('.card').filter({ hasText: 'GitHub Workflow Activity' })).toBeVisible();
});
