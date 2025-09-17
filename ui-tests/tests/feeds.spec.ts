import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Feeds management', () => {
  test('add/toggle/check/delete feed', async ({ page }) => {
    await page.goto('/feeds');
    await expect(page.getByRole('heading', { name: 'Feeds' })).toBeVisible();

    // Use local RSS file for deterministic parsing
    const rssPath = path.resolve(process.cwd(), '..', 'daily-digest.xml');
    const fileUrl = 'file://' + rssPath;

    await page.fill('input[name="feed_url"]', fileUrl);
    // Leave title blank to trigger auto-fill
    await Promise.all([
      page.waitForURL('**/feeds'),
      page.click('button:has-text("Add Feed")')
    ]);

    await expect(page.locator('text=Feed added')).toBeVisible();

    // Row should show parsed title
    await expect(page.locator('td').filter({ hasText: 'Daily AI & Tech Digest' })).toBeVisible();

    // Find the row and click Deactivate (toggle)
    const row = page.locator('tr', { hasText: 'Daily AI & Tech Digest' }).first();
    const toggleBtn = row.locator('form[action^="/feeds/"][action$="/toggle"] button');
    await toggleBtn.click();
    await expect(page.locator('text=Feed deactivated')).toBeVisible();

    // Activate again
    await toggleBtn.click();
    await expect(page.locator('text=Feed activated')).toBeVisible();

    // Check feed
    await row.locator('form[action$="/check"] button').click();
    await expect(page.locator('text=Feed OK')).toBeVisible();

    // Soft delete (deactivate)
    await row.locator('form[action$="/delete"] button').click();
    await expect(page.locator('text=Feed deactivated (soft delete)')).toBeVisible();

    // Attempt to add duplicate feed URL -> expect error banner
    await page.fill('input[name="feed_url"]', fileUrl);
    await Promise.all([
      page.waitForURL('**/feeds'),
      page.click('button:has-text("Add Feed")')
    ]);
    await expect(page.locator('text=Feed already exists')).toBeVisible();

    // Add a YouTube "feed" (manual title) to assert grouping
    await page.fill('input[name="feed_url"]', 'https://www.youtube.com/channel/UC123456');
    await page.fill('input[name="title"]', 'YouTube Test');
    await Promise.all([
      page.waitForURL('**/feeds'),
      page.click('button:has-text("Add Feed")')
    ]);
    // Should appear in the YouTube Feeds table
    const ytSection = page.locator('h3', { hasText: 'YouTube Feeds' }).locator('xpath=..');
    await expect(ytSection.locator('td').filter({ hasText: 'YouTube Test' })).toBeVisible();
  });
});
