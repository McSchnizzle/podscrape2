import { test, expect } from '@playwright/test';

/**
 * Auth guard matrix for kanban #2846 -- confirms middleware.ts (and the
 * lib/auth-guard.ts requireAuth() route guard behind it) actually closes
 * the /api/* auth hole from #2710, without breaking the public feeds.
 *
 * Runs against a live `next start` (see ui-tests/README or the kanban #2846
 * operator runbook for env vars: SESSION_SECRET, ADMIN_PASSWORD,
 * SUPABASE_URL, SUPABASE_SERVICE_ROLE, DATABASE_URL).
 */

const PUBLIC_GET_PATHS = ['/login', '/api/health', '/api/rss/daily-digest', '/api/rss/ai-tech-digest'];

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
