# Vercel Implementation Learnings

## Issue: Headers Configuration for Static Files Not Working in `vercel dev`

### Problem Discovered (Phase 6)
While implementing static RSS feed serving, discovered that headers configured in `vercel.json` don't work as expected in local development with `vercel dev`.

**Symptoms:**
- `Content-Type: application/xml` instead of `application/rss+xml; charset=utf-8`
- `cache-control: public, max-age=0, must-revalidate` instead of `max-age=300`
- Headers configuration appears to be ignored by local dev server

### Root Cause Analysis

1. **Vercel Dev Server Limitation**: The `vercel dev` command doesn't perfectly emulate production header behavior for static files
2. **Default Static File Behavior**: Vercel defaults to `public, max-age=0, must-revalidate` for static files to prevent local browser caching
3. **Configuration Syntax Issues**: Using `routes` with `headers` causes conflicts - must use `rewrites` instead

### Configuration Requirements

#### Correct vercel.json Structure (No Conflicts)
```json
{
  "version": 2,
  "rewrites": [
    {
      "source": "/audio/(.*)",
      "destination": "/api/audio/$1"
    }
  ],
  "headers": [{
    "source": "/daily-digest.xml",
    "headers": [
      { "key": "Content-Type", "value": "application/rss+xml; charset=utf-8" },
      { "key": "Cache-Control", "value": "public, max-age=300" }
    ]
  }]
}
```

#### Configuration Conflicts to Avoid
- Cannot use `routes` together with `headers`, `rewrites`, `redirects`, `cleanUrls`, or `trailingSlash`
- Error message: "If `rewrites`, `redirects`, `headers`, `cleanUrls` or `trailingSlash` are used, then `routes` cannot be present"

### Static File Header Behavior

#### Production vs Local Development
- **Production**: Headers in `vercel.json` are properly applied to static files
- **Local Dev**: Headers may not be applied correctly with `vercel dev` command
- **Default Behavior**: Static files get `public, max-age=0, must-revalidate` by default

#### Vercel's Default Caching Strategy
- Static files automatically cached at edge for 31 days after first request
- Default Cache-Control prevents local browser caching: `public, max-age=0, must-revalidate`
- Custom headers can override defaults in production but may not work in local dev

### Testing Strategy

#### Local Development Testing
1. **Accept Limited Local Testing**: `vercel dev` may not perfectly match production headers
2. **Focus on Basic Functionality**: Verify static files are served correctly (200 status, correct content)
3. **Validate XML Structure**: Ensure RSS feed is well-formed and accessible

#### Production Validation Required
1. **Deploy to Vercel**: Headers configuration only fully testable in production environment
2. **Use CI Validation**: Implement automated header checks in CI pipeline
3. **Real-World Testing**: Test with actual podcatchers after deployment

### Recommended Approach for Phase 6

1. **Configuration First**: Ensure `vercel.json` is correct with `rewrites` instead of `routes`
2. **Basic Local Testing**: Verify static file serving works (ignore header mismatch in dev)
3. **Production-Ready CI**: Implement CI validation that tests production endpoints
4. **Post-Deploy Verification**: Always test headers on actual Vercel deployment

### CI Validation Requirements

Since local dev server doesn't reliably test headers, CI must validate:
- HTTP 200 status code
- Correct Content-Type header
- Cache-Control header presence
- ETag or Last-Modified header presence
- XML well-formedness

### Debugging Commands

```bash
# Local testing (limited header validation)
curl -I http://localhost:3000/daily-digest.xml

# Production testing (full header validation)  
curl -I https://podcast.paulrbrown.org/daily-digest.xml

# XML validation
xmllint --noout public/daily-digest.xml

# Content verification
curl -s http://localhost:3000/daily-digest.xml | head -5
```

### Key Learnings

1. **Don't Trust Local Dev for Headers**: Vercel dev server doesn't perfectly emulate production header behavior
2. **CI Testing is Critical**: Production header validation must be automated in CI
3. **Configuration Syntax Matters**: Use `rewrites` not `routes` when using headers
4. **Static Files Need Special Handling**: Default Vercel behavior prevents browser caching
5. **Production Testing Required**: Always validate headers on actual Vercel deployment

### Future Reference

For any static file header configuration:
1. Use `rewrites` instead of `routes` in `vercel.json`
2. Test locally for basic functionality only
3. Rely on CI and production testing for header validation
4. Expect different behavior between `vercel dev` and production