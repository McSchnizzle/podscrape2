import { test, expect } from '@playwright/test';

test('script lab loads instructions', async ({ page }) => {
  await page.goto('/script-lab');
  await expect(page.getByRole('heading', { name: 'Script Lab' })).toBeVisible();
  await expect(page.locator('select').first()).toBeVisible();
});
