import { test, expect } from '@playwright/test';

test.describe('Retention settings', () => {
  test('edit and persist retention days', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    // Change one retention value (scripts) and save
    const scripts = page.locator('input[name="ret_scripts"]');
    await scripts.fill('13');
    await page.getByRole('button', { name: 'Save' }).click();
    // Back to settings, verify value
    await page.goto('/settings');
    await expect(page.locator('input[name="ret_scripts"]')).toHaveValue('13');
  });
});

