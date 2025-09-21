import { test, expect } from '@playwright/test';

test.describe('Dashboard smoke test', () => {
  test('shows system health and pipeline status cards', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.locator('.card').filter({ hasText: 'System Health' })).toBeVisible();
    await expect(page.locator('.card').filter({ hasText: 'Pipeline Status' })).toBeVisible();
    await expect(page.locator('.card').filter({ hasText: 'Recent Activity' })).toBeVisible();
  });
});
