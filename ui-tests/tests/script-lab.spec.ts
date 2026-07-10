import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test('script lab loads instructions', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/script-lab');
  await expect(page.getByRole('heading', { name: 'Script Lab' })).toBeVisible();
  await expect(page.locator('select').first()).toBeVisible();
});
