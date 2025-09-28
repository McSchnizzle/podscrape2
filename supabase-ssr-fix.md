# Supabase SSR OAuth Fix Implementation Plan

## Problem Summary
The PKCE "code verifier should be non-empty" error occurs because the current OAuth implementation uses only client-side Supabase authentication without proper server-side integration required for Next.js App Router.

## Root Cause
1. Using deprecated `@supabase/auth-helpers` pattern with client-only setup
2. Missing `@supabase/ssr` package for proper server-side authentication
3. PKCE code verifier not properly stored/retrieved between client and server
4. OAuth callback route unable to access server-side cookie storage

## Implementation Tasks

### ✅ Step 1: Install Required Package
- [x] Install `@supabase/ssr` package for proper server-side authentication

### ✅ Step 2: Create Server and Client Utilities
- [x] Create `utils/supabase/client.ts` - Browser client for Client Components
- [x] Create `utils/supabase/server.ts` - Server client with cookie handling for Server Components/Route Handlers
- [x] Create `utils/supabase/middleware.ts` - Middleware helper for token refresh

### ✅ Step 3: Implement Middleware
- [x] Create `middleware.ts` at project root for:
  - Refreshing expired auth tokens
  - Passing tokens to Server Components
  - Updating browser cookies with refreshed tokens

### ✅ Step 4: Fix OAuth Callback Route
- [x] Update `/app/auth/callback/route.ts` to:
  - Use server client from `utils/supabase/server.ts`
  - Properly exchange OAuth code for session using `exchangeCodeForSession()`
  - Handle PKCE flow correctly with cookie storage
  - Add proper error handling and logging

### ✅ Step 5: Update AuthProvider
- [x] Modify `utils/supabase-auth.ts` to:
  - Use new client from `utils/supabase/client.ts`
  - Restore callback redirect to `/auth/callback`
  - Simplified client configuration (SSR package handles PKCE automatically)

### ✅ Step 6: Environment Variables Check
- [x] Verified all required environment variables are set in Vercel:
  - `NEXT_PUBLIC_SUPABASE_URL` ✅ (confirmed working)
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY` ✅ (recently fixed)
  - `SUPABASE_SERVICE_ROLE` ✅ (for admin operations)
- [x] No additional SSR-specific environment variables needed

### 🔄 Step 7: Update Version and Deploy
- [x] Increment version to 1.11 in `web_ui_hosted/app/version.ts`
- [ ] Commit all changes with descriptive message
- [ ] Push to trigger Vercel deployment
- [ ] Test OAuth login after deployment

## Key Technical Details

### Why This Will Work
- Based on official Supabase documentation for Next.js 14 App Router
- Uses production-proven `@supabase/ssr` package
- Proper client/server separation with cookie-based session management
- Follows patterns from thousands of successful deployments

### Environment Variables Status
The existing environment variables should be sufficient:
- `NEXT_PUBLIC_SUPABASE_URL` - Public Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Public anonymous key for client access
- `SUPABASE_SERVICE_ROLE` - Service role key for admin operations (web UI only)

No additional SSR-specific environment variables are required.

## Testing Plan
1. Deploy changes to Vercel
2. Navigate to admin panel: https://podcast.paulrbrown.org/
3. Click "Sign in with Google"
4. Verify successful authentication for brownpr0@gmail.com
5. Confirm proper redirect and session persistence

## Rollback Plan
If OAuth still fails after implementation:
1. Revert to previous callback route implementation
2. Consider switching to email/password authentication temporarily
3. Debug with Supabase auth logs and Vercel function logs

## References
- [Supabase Next.js SSR Documentation](https://supabase.com/docs/guides/auth/server-side/nextjs)
- [Working Example Repository](https://github.com/SarathAdhi/next-supabase-auth)
- [Supabase SSR Package](https://www.npmjs.com/package/@supabase/ssr)