import { test, expect } from '@playwright/test';

test.describe('Publishing UI', () => {
  test('lists digests with asset status and actions', async ({ page }) => {
    await page.goto('/publishing');
    await expect(page.getByRole('heading', { name: 'Publishing' })).toBeVisible();
    // Table headers
    await expect(page.getByText('Date')).toBeVisible();
    await expect(page.getByText('Topic')).toBeVisible();
    await expect(page.getByText('MP3')).toBeVisible();
    await expect(page.getByText('Asset')).toBeVisible();
    await expect(page.getByText('Actions')).toBeVisible();
    // Days filter present
    await expect(page.getByLabel('Days')).toBeVisible();
  });
});

