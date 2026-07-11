import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

// Rewritten for the kanban #2846 Phase 2 dashboard rebuild -- the old
// "System Health" / "Pipeline Status" / "Recent Activity" panels this spec
// used to assert on were the inaccurate panels Paul asked to throw away.
// This checks the new hand-verified summary cards instead.
test.describe('Dashboard smoke test', () => {
  test('shows the rebuilt pipeline summary cards', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Latest published episode')).toBeVisible();
    await expect(page.getByText("Tonight's pipeline readiness")).toBeVisible();
    await expect(page.getByText('Last pipeline outcome')).toBeVisible();
    await expect(page.getByText('Active feeds')).toBeVisible();
    await expect(page.getByText('Active watch themes')).toBeVisible();
  });
});
