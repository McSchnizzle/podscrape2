import { test, expect } from '@playwright/test';

test.describe('Dashboard sections render', () => {
  test('shows settings, last run, rss items, undigested, failed sections', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.locator('text=Content Filtering')).toBeVisible();
    await expect(page.locator('text=Audio Processing')).toBeVisible();
    await expect(page.locator('text=Last Run')).toBeVisible();
    await expect(page.locator('text=RSS Items')).toBeVisible();
    await expect(page.locator('text=Transcribed Not Yet Digested')).toBeVisible();
    await expect(page.locator('text=Failed Episodes')).toBeVisible();
  });
});

