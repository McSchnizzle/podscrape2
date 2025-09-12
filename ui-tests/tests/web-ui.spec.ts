import { test, expect } from '@playwright/test';

test.describe('Web UI settings flow', () => {
  test('loads dashboard and settings, updates values, and persists', async ({ page }) => {
    // Dashboard
    await page.goto('/');
    await expect(page.locator('text=Podcast Digest Web UI')).toBeVisible();
    await expect(page.locator('text=Content Filtering')).toBeVisible();

    // Go to settings
    await page.goto('/settings');
    await expect(page.locator('text=Settings')).toBeVisible();

    // Read current values
    const threshInput = page.locator('input[name="score_threshold"]');
    const maxEpInput = page.locator('input[name="max_episodes_per_digest"]');
    const chunkInput = page.locator('input[name="chunk_duration_minutes"]');

    // Set new values
    await threshInput.fill('0.70');
    await maxEpInput.fill('3');
    await chunkInput.fill('5');

    await Promise.all([
      page.waitForURL('**/settings'),
      page.click('button[type="submit"]')
    ]);

    // Success banner appears
    await expect(page.locator('text=Settings saved')).toBeVisible();

    // Back to dashboard, values reflected
    await page.goto('/');
    await expect(page.locator('text=Score Threshold:').locator('xpath=..')).toContainText('0.7');
    await expect(page.locator('text=Max Episodes per Digest:').locator('xpath=..')).toContainText('3');
    await expect(page.locator('text=Chunk Duration (minutes):').locator('xpath=..')).toContainText('5');
  });
});

