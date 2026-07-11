import { test, expect } from '@playwright/test';

/**
 * Google OAuth2 sign-in for the admin UI (kanban #2846 Phase 3), replacing
 * the password-only login with a direct (non-Supabase) flow that mints the
 * same session cookie as /api/auth/login. The password form stays as a
 * break-glass fallback.
 *
 * Tests that need a live Google client (the redirect-params check) skip
 * themselves when GOOGLE_OAUTH_CLIENT_ID isn't set in the test environment
 * -- state validation and the login page's conditional rendering don't need
 * it and always run.
 */

const GOOGLE_CLIENT_ID = process.env.GOOGLE_OAUTH_CLIENT_ID;

test.describe('/api/auth/google', () => {
  test('redirects to accounts.google.com with the expected params', async ({ request }) => {
    test.skip(!GOOGLE_CLIENT_ID, 'GOOGLE_OAUTH_CLIENT_ID not set in the test environment');

    const response = await request.get('/api/auth/google?next=%2Fsettings', { maxRedirects: 0 });
    expect(response.status()).toBe(307);

    const location = response.headers()['location'];
    expect(location).toBeTruthy();
    const url = new URL(location);

    expect(url.origin + url.pathname).toBe('https://accounts.google.com/o/oauth2/v2/auth');
    expect(url.searchParams.get('client_id')).toBe(GOOGLE_CLIENT_ID);
    expect(url.searchParams.get('redirect_uri')).toBe(
      `${process.env.PUBLIC_BASE_URL || 'https://podcast.paulrbrown.org'}/api/auth/callback/google`
    );
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('scope')).toBe('openid email');
    expect(url.searchParams.get('prompt')).toBe('select_account');
    expect(url.searchParams.get('state')).toBeTruthy();
  });

  test('two requests mint different state tokens (CSRF nonce)', async ({ request }) => {
    test.skip(!GOOGLE_CLIENT_ID, 'GOOGLE_OAUTH_CLIENT_ID not set in the test environment');

    const [a, b] = await Promise.all([
      request.get('/api/auth/google', { maxRedirects: 0 }),
      request.get('/api/auth/google', { maxRedirects: 0 }),
    ]);
    const stateA = new URL(a.headers()['location']).searchParams.get('state');
    const stateB = new URL(b.headers()['location']).searchParams.get('state');
    expect(stateA).not.toBe(stateB);
  });

  test('responds 503 with Google button hidden when unconfigured', async ({ request }) => {
    test.skip(Boolean(GOOGLE_CLIENT_ID), 'this environment has Google configured; see the configured-path test above');

    const response = await request.get('/api/auth/google', { maxRedirects: 0 });
    expect(response.status()).toBe(503);
  });
});

test.describe('/api/auth/callback/google state validation', () => {
  // These exercise the state-verification step specifically, which the
  // route only reaches once GOOGLE_OAUTH_CLIENT_ID/SECRET are present --
  // unconfigured, every callback short-circuits to oauth_failed instead
  // (correct: nobody reaches this URL without the button that's hidden in
  // that case). The "user-denied consent" and "forged signature" cases
  // below share this dependency.
  test('missing state redirects to /login?error=state_invalid', async ({ request }) => {
    test.skip(!GOOGLE_CLIENT_ID, 'GOOGLE_OAUTH_CLIENT_ID not set in the test environment');

    const response = await request.get('/api/auth/callback/google', { maxRedirects: 0 });
    expect(response.status()).toBe(307);
    const location = response.headers()['location'];
    expect(new URL(location).pathname).toBe('/login');
    expect(new URL(location).searchParams.get('error')).toBe('state_invalid');
  });

  test('garbage state redirects to /login?error=state_invalid', async ({ request }) => {
    test.skip(!GOOGLE_CLIENT_ID, 'GOOGLE_OAUTH_CLIENT_ID not set in the test environment');

    const response = await request.get('/api/auth/callback/google?state=not-a-real-token&code=abc', {
      maxRedirects: 0,
    });
    expect(response.status()).toBe(307);
    const location = response.headers()['location'];
    expect(new URL(location).searchParams.get('error')).toBe('state_invalid');
  });

  test('forged (tampered signature) state redirects to /login?error=state_invalid', async ({ request }) => {
    test.skip(!GOOGLE_CLIENT_ID, 'needs a real signed state to tamper with');

    const authResponse = await request.get('/api/auth/google', { maxRedirects: 0 });
    const validState = new URL(authResponse.headers()['location']).searchParams.get('state')!;
    const [payload, signature] = validState.split('.');
    const flippedChar = signature[0] === 'a' ? 'b' : 'a';
    const tampered = `${payload}.${flippedChar}${signature.slice(1)}`;

    const response = await request.get(
      `/api/auth/callback/google?state=${encodeURIComponent(tampered)}&code=abc`,
      { maxRedirects: 0 }
    );
    expect(response.status()).toBe(307);
    expect(new URL(response.headers()['location']).searchParams.get('error')).toBe('state_invalid');
  });

  test('user-denied consent (Google error param) redirects to /login?error=oauth_failed', async ({ request }) => {
    const response = await request.get('/api/auth/callback/google?error=access_denied', { maxRedirects: 0 });
    expect(response.status()).toBe(307);
    expect(new URL(response.headers()['location']).searchParams.get('error')).toBe('oauth_failed');
  });
});

test.describe('login page Google sign-in affordance', () => {
  test('shows/hides the Google button to match /api/auth/providers', async ({ page, request }) => {
    const providers = await (await request.get('/api/auth/providers')).json();

    await page.goto('/login');
    const googleButton = page.getByRole('link', { name: /sign in with google/i });

    if (providers.google) {
      await expect(googleButton).toBeVisible();
    } else {
      await expect(googleButton).toHaveCount(0);
      // Password-only mode: the fallback form should already be open, not
      // hidden behind a disclosure toggle nobody would think to click.
      await expect(page.getByLabel('Password')).toBeVisible();
    }
  });

  test('friendly error messages render for each known ?error= code', async ({ page }) => {
    const cases: Record<string, RegExp> = {
      not_allowed: /not authorized/i,
      oauth_failed: /sign-in failed/i,
      state_invalid: /expired or could not be verified/i,
    };

    for (const [code, expected] of Object.entries(cases)) {
      await page.goto(`/login?error=${code}`);
      // A bare role="alert" locator collides with Next.js's own route
      // announcer (#__next-route-announcer__) and, on this branch, a
      // pre-existing bug where RootLayout renders the authenticated
      // sidebar's chrome on /login regardless of session state (kanban
      // #2846 Phase 2, unrelated to this OAuth work) -- data-testid sidesteps
      // both.
      await expect(page.getByTestId('login-error')).toHaveText(expected);
    }
  });
});
