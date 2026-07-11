import { Page, test } from '@playwright/test';

/**
 * Logs the given page in via the admin session-auth flow added in kanban
 * #2846 Phase 1. Every admin page/route now sits behind middleware.ts, so
 * any spec that navigates to an admin page must call this first (or it
 * just observes the /login redirect and every assertion fails).
 *
 * FAILS (does not skip) when ADMIN_PASSWORD isn't set, so a misconfigured
 * run can't silently green-light regressions (codex review, #2846 Phase 2).
 * Set PLAYWRIGHT_ALLOW_SKIP_AUTH=1 for deliberate password-less local runs.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  const password = process.env.ADMIN_PASSWORD;
  if (!password) {
    if (process.env.PLAYWRIGHT_ALLOW_SKIP_AUTH === '1') {
      test.skip(true, 'ADMIN_PASSWORD not set; skip explicitly allowed');
    }
    throw new Error(
      'ADMIN_PASSWORD is not set in the test environment. Authenticated specs ' +
      'require it (set PLAYWRIGHT_ALLOW_SKIP_AUTH=1 to skip deliberately).'
    );
  }

  await page.goto('/login');
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 10_000 });
}
