import { test, expect, type Page } from '@playwright/test';

/**
 * The password form is now a collapsed "Use fallback password" disclosure
 * when Google sign-in is configured (kanban #2846 Phase 3) -- open it
 * before interacting with the password field. A no-op when Google isn't
 * configured, since the fallback form is already open in that case.
 */
async function openPasswordFallback(page: Page) {
  const toggle = page.getByRole('button', { name: /use fallback password/i });
  const passwordField = page.getByLabel('Password');
  // /login resolves its layout asynchronously (client-side fetch to
  // /api/auth/providers) into one of two states: password-only (the field
  // is already visible) or Google-primary (the field is hidden behind the
  // toggle). Wait for either to settle before deciding -- a bare
  // isVisible() check races the fetch and always sees neither yet.
  await Promise.race([
    toggle.waitFor({ state: 'visible', timeout: 15_000 }).catch(() => {}),
    passwordField.waitFor({ state: 'visible', timeout: 15_000 }).catch(() => {}),
  ]);
  if (await toggle.isVisible().catch(() => false)) {
    await toggle.click();
  }
}

/**
 * Auth guard matrix for kanban #2846 -- confirms middleware.ts (and the
 * lib/auth-guard.ts requireAuth() route guard behind it) actually closes
 * the /api/* auth hole from #2710, without breaking the public feeds.
 *
 * Runs against a live `next start` (see ui-tests/README or the kanban #2846
 * operator runbook for env vars: SESSION_SECRET, ADMIN_PASSWORD,
 * SUPABASE_URL, SUPABASE_SERVICE_ROLE, DATABASE_URL). Optionally
 * GOOGLE_OAUTH_CLIENT_ID/SECRET (kanban #2846 Phase 3, see
 * google-oauth.spec.ts) -- when set, the password form on /login moves
 * behind a "Use fallback password" disclosure, which openPasswordFallback()
 * above accounts for.
 */

const PUBLIC_GET_PATHS = [
  '/login',
  '/api/health',
  '/api/rss/daily-digest',
  '/api/rss/ai-tech-digest',
  // Has its own CRON_SECRET check and a live systemd-timer caller with no
  // session cookie -- must stay reachable without one (codex review, #2846).
  '/api/heartbeat',
  // Public regardless of GOOGLE_OAUTH_* config: unconfigured -> 503 JSON,
  // configured -> 307 to accounts.google.com. Neither is a 401 or a
  // /login redirect, so it fits the same generic assertion as the paths
  // above. The other new OAuth leg (/api/auth/callback/google) does NOT
  // belong here -- called bare it legitimately 302s to /login?error=...,
  // which the assertion below would flag. It gets its own coverage in
  // google-oauth.spec.ts (kanban #2846 Phase 3).
  '/api/auth/google',
  '/api/auth/providers',
];

const ADMIN_PAGE_PATHS = ['/dashboard', '/settings', '/topics'];

const ADMIN_API_PATHS = ['/api/episodes', '/api/feeds', '/api/tasks', '/api/settings'];

test.describe('public paths are reachable without a session', () => {
  for (const path of PUBLIC_GET_PATHS) {
    test(`GET ${path} does not require auth`, async ({ request }) => {
      // Asserts the auth guard specifically (not >=400 in general) -- these
      // routes can still legitimately 5xx in an environment where the data
      // layer (DATABASE_URL/SUPABASE_URL) isn't wired up, which is not an
      // auth regression.
      const response = await request.get(path, { maxRedirects: 0 });
      expect(response.status(), `${path} should not require auth`).not.toBe(401);
      if (response.status() >= 300 && response.status() < 400) {
        const location = response.headers()['location'] || '';
        expect(location, `${path} should not redirect to /login`).not.toContain('/login');
      }
    });
  }
});

test.describe('admin API routes are blocked without a session', () => {
  for (const path of ADMIN_API_PATHS) {
    test(`GET ${path} returns 401 without a cookie`, async ({ request }) => {
      const response = await request.get(path);
      expect(response.status()).toBe(401);
      const body = await response.json();
      expect(body.error).toBeTruthy();
    });
  }
});

test.describe('admin pages redirect to /login without a session', () => {
  for (const path of ADMIN_PAGE_PATHS) {
    test(`GET ${path} redirects to /login`, async ({ page }) => {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login(\?.*)?$/);
    });
  }
});

test('wrong password is rejected', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { password: 'definitely-not-the-password' },
  });
  expect(response.status()).toBe(401);
});

test('correct password sets a session cookie that unlocks admin routes', async ({ page, request }) => {
  const password = process.env.ADMIN_PASSWORD;
  test.skip(!password, 'ADMIN_PASSWORD not set in the test environment');

  const loginResponse = await request.post('/api/auth/login', {
    data: { password },
  });
  expect(loginResponse.status()).toBe(200);

  const cookies = await request.storageState();
  expect(cookies.cookies.some((c) => c.name === 'podcast_admin_session')).toBe(true);

  const meResponse = await request.get('/api/auth/me');
  expect(meResponse.status()).toBe(200);

  const adminApiResponse = await request.get('/api/tasks/stats');
  expect(adminApiResponse.status()).not.toBe(401);
});

test.describe('login next= param is constrained to same-origin relative paths', () => {
  const password = process.env.ADMIN_PASSWORD;

  const OPEN_REDIRECT_ATTEMPTS = ['https://evil.example.com', '//evil.example.com', '/\\evil.example.com'];

  for (const nextParam of OPEN_REDIRECT_ATTEMPTS) {
    test(`next=${nextParam} does not redirect off-origin`, async ({ page }) => {
      test.skip(!password, 'ADMIN_PASSWORD not set in the test environment');

      await page.goto(`/login?next=${encodeURIComponent(nextParam)}`);
      const expectedOrigin = new URL(page.url()).origin;

      await openPasswordFallback(page);
      await page.getByLabel('Password').fill(password!);
      await page.getByRole('button', { name: /sign in/i }).click();
      await page.waitForURL((url) => url.pathname !== '/login', { timeout: 10_000 });

      expect(new URL(page.url()).origin, `next=${nextParam} should not escape the app origin`).toBe(
        expectedOrigin
      );
    });
  }

  test('next=/dashboard (a legitimate same-origin path) is honored', async ({ page }) => {
    test.skip(!password, 'ADMIN_PASSWORD not set in the test environment');

    await page.goto('/login?next=%2Fdashboard');
    await openPasswordFallback(page);
    await page.getByLabel('Password').fill(password!);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
