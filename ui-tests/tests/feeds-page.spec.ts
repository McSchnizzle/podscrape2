import { test, expect } from '@playwright/test';

test('feeds page loads', async ({ page }) => {
  await page.goto('/feeds');
  await page.waitForLoadState('domcontentloaded');
  const heading = page.getByRole('heading', { name: 'Feeds', exact: true });
  if (await heading.count()) {
    await expect(heading).toBeVisible();
  } else {
    await expect(page.locator('text=Loading feeds...')).toBeVisible();
  }
});
