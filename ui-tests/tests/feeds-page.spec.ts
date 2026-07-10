import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('feeds page loads', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/feeds');
  // The page renders a loading state briefly then swaps to the heading once
  // /api/feeds resolves -- wait directly for the end state instead of
  // racing a count() check against a "Loading feeds..." string that may
  // already be gone by the time we look (this was flaky before the auth
  // gate was added too, just never noticed since the test never got past
  // the login redirect).
  await expect(page.getByRole('heading', { name: 'Feeds', exact: true })).toBeVisible({ timeout: 10_000 });
});
