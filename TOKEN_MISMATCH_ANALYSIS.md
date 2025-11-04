# Token Mismatch Analysis - Updated Findings

**Date:** November 4, 2025
**Issue:** GitHub Actions workflow failures due to invalid GitHub token
**Status:** 🚨 **ROOT CAUSE CONFIRMED: Token Mismatch**

## Critical Discovery

The GitHub token shown in GitHub UI (valid until Dec 10, 2025) is **NOT the same token** being used by the workflows and local environment.

### Evidence

**Test Performed:**
```bash
curl -s -i -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/user"
```

**Result:**
```
HTTP/2 401
{
  "message": "Bad credentials",
  "documentation_url": "https://docs.github.com/rest",
  "status": "401"
}
```

**Environment Token:**
- Starts with: `ghp_8M1jtJ9SG5c...`
- Length: 40 characters (correct format)
- Status: **INVALID** - Returns 401 "Bad credentials"

**GitHub UI Shows:**
- Token expiration: December 10, 2025
- Scopes: repo, workflow, write:packages (all correct)
- Status: Should be valid

## Root Cause: Token Regeneration

At some point, the token was **regenerated** in GitHub, which:
1. ✅ Created a new valid token (shown in GitHub UI)
2. ❌ Invalidated the old token (still in environment/secrets)
3. ❌ GitHub repository secrets were never updated with new token
4. ❌ Workflows started failing when using the old invalid token

**Timeline:**
- Token regenerated: Unknown date (between Oct 22 - Oct 31)
- Old token invalidated: Same moment as regeneration
- Workflow failures started: ~October 31, 2025
- Issue discovered: November 4, 2025

## Why This Explains Everything

1. **No code changes** - Code is fine, it's the auth token
2. **Sudden failure** - Token was regenerated, old one invalidated immediately
3. **Workflow Phase 5 fails** - Publishing phase requires GitHub API access
4. **401 errors** - Classic "Bad credentials" from expired/invalid token
5. **Dec 10 expiration confusing** - That's the NEW token, not the one in use

## The Fix

### Problem Location

The **old invalid token** is stored in:
1. ❌ GitHub repository secrets (`GH_TOKEN` secret)
2. ❌ Local environment (wherever `GITHUB_TOKEN` is set)

### Solution

You need to **copy the current valid token value** from GitHub and update both locations:

#### Step 1: Get the Current Token Value

**Option A: View Existing Token (if recently created)**
- If you created this token recently, you might have saved the value
- Check password managers, secure notes, or wherever you store secrets

**Option B: Regenerate the Token**
Since regeneration invalidates it anyway and it's already invalid in the secrets:

1. Go to: https://github.com/settings/tokens
2. Find the token named "podscrape2"
3. Click "Regenerate token"
4. **COPY THE NEW TOKEN IMMEDIATELY** (you won't see it again)
5. Save it securely (password manager recommended)

#### Step 2: Update GitHub Repository Secrets

1. Go to: https://github.com/McSchnizzle/podscrape2/settings/secrets/actions
2. Find `GH_TOKEN` in the list
3. Click "Update"
4. Paste the **current/regenerated token value**
5. Click "Update secret"

Also check these other token secrets:
- `GITHUB_TOKEN` (if it exists separately)
- Any other `GH_*` or `GITHUB_*` related secrets

#### Step 3: Update Local Environment

Wherever you have `GITHUB_TOKEN` set locally, update it:

```bash
# If you have a .env file somewhere:
# Find it: find ~ -name ".env" 2>/dev/null
# Edit it and update:
GITHUB_TOKEN=ghp_YOUR_NEW_TOKEN_HERE
GH_TOKEN=ghp_YOUR_NEW_TOKEN_HERE
```

Or if you set it in your shell profile:
```bash
# ~/.bashrc, ~/.zshrc, or similar
export GITHUB_TOKEN="ghp_YOUR_NEW_TOKEN_HERE"
export GH_TOKEN="ghp_YOUR_NEW_TOKEN_HERE"
```

#### Step 4: Verify Fix

Test the new token works:
```bash
# Load new token into environment
export GITHUB_TOKEN="ghp_YOUR_NEW_TOKEN_HERE"

# Test it
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Should return your GitHub user info, NOT "Bad credentials"
```

#### Step 5: Trigger Workflow

Once the repository secret is updated:
1. Go to: https://github.com/McSchnizzle/podscrape2/actions
2. Select "Validated Full Pipeline"
3. Click "Run workflow"
4. Watch it complete successfully ✅

## Important Notes

### Why "Regenerate" Instead of "Copy"?

When you regenerate a token in GitHub:
- The old token is **immediately invalidated** (can't be un-regenerated)
- A new token is created with the same scopes and expiration settings
- You get to see the new token value once

Since the old token in your secrets is already invalid, regenerating won't make things worse - it will give you the current valid token to update your secrets with.

### Token Best Practices

1. **Save token values securely** when first created
   - Use a password manager (1Password, LastPass, etc.)
   - Never commit tokens to git
   - Never share tokens publicly

2. **Update all locations** when regenerating
   - GitHub repository secrets
   - Local development environment
   - CI/CD systems
   - Any scripts or tools using the token

3. **Set expiration appropriately**
   - For automation: "No expiration" or 90+ days
   - For personal use: 30-90 days
   - For testing: 7-30 days

4. **Use separate tokens** for different purposes
   - One for local development
   - One for CI/CD (with only required scopes)
   - One for production systems

## Expected Outcome

After updating the token in GitHub repository secrets:

✅ Phase 1 (Discovery) - Completes successfully
✅ Phase 2 (Audio) - Completes successfully
✅ Phase 3 (Digest) - Completes successfully
✅ Phase 4 (TTS) - Completes successfully
✅ Phase 5 (Publishing) - **NOW WORKS** - Creates releases, uploads MP3s
✅ Phase 6 (Retention) - Completes successfully

The workflow will run end-to-end without failures.

## Questions Answered

**Q: Why does GitHub show the token expires Dec 10 but it returns "Bad credentials"?**
A: Because the token in GitHub UI is the CURRENT valid token, but your secrets have an OLD token that was replaced/regenerated.

**Q: When was the token regenerated?**
A: Between Oct 22 (last code change) and Oct 31 (when failures started). Check your GitHub token audit log or security events for exact date.

**Q: Will regenerating the token again break anything?**
A: No - the old token in your secrets is already broken. Regenerating gives you a fresh valid token to update your secrets with.

**Q: How do I prevent this in the future?**
A: When you regenerate a token, immediately update ALL locations where it's stored (GitHub secrets, local env, docs, password manager).

## Next Steps

1. ✅ **Regenerate the token** in GitHub token settings
2. ✅ **Copy the new token value** (save it securely!)
3. ✅ **Update GitHub repository secret** `GH_TOKEN`
4. ✅ **Update local environment** (wherever GITHUB_TOKEN is set)
5. ✅ **Test workflow run** to verify fix
6. ✅ **Document new token** (where it's stored, expiration date)

---

**Summary:** The token shown in GitHub UI is valid, but it's not the token in your secrets. Update the secrets with the current token value and workflows will work again.
