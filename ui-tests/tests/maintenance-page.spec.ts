import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

// NOTE: this page has been "Task Management" (not a pipeline/GitHub activity
// view) since before kanban #2846 Phase 2 -- confirmed via git history on
// app/maintenance/page.tsx. The previous version of this spec asserted on
// "Trigger Full Pipeline" / "Supabase Pipeline Runs" / "GitHub Workflow
// Activity", none of which exist on this page; it was already failing
// (silently, since nothing had exercised the auth-gated suite). Rewritten
// to match the page's actual, current content.
test('maintenance page lists task stats and filters', async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto('/maintenance');
  await expect(page.getByRole('heading', { name: 'Task Management' })).toBeVisible();
  await expect(page.getByText('Total Tasks', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: /Add Task/i })).toBeVisible();
  await expect(page.getByPlaceholder('Search tasks...')).toBeVisible();
});
