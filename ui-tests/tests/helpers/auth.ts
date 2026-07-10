import { Page, test } from '@playwright/test';

/**
 * Logs the given page in via the admin session-auth flow added in kanban
 * #2846 Phase 1. Every admin page/route now sits behind middleware.ts, so
 * any spec that navigates to an admin page must call this first (or it
 * just observes the /login redirect and every assertion fails).
 *
 * Skips the test (not fails) when ADMIN_PASSWORD isn't set in the test
 * environment, matching the pattern already used in auth-middleware.spec.ts.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  const password = process.env.ADMIN_PASSWORD;
  test.skip(!password, 'ADMIN_PASSWORD not set in the test environment');

  await page.goto('/login');
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 10_000 });
}
