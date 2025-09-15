import { test, expect } from '@playwright/test';

test.describe('Web UI Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the home page
    await page.goto('http://127.0.0.1:5001');

    // Wait for the page to be ready
    await expect(page.locator('h1')).toContainText('Podcast Digest Web UI');
  });

  test('Dashboard tab loads correctly', async ({ page }) => {
    // Click on Dashboard tab
    await page.click('a[href="/"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the dashboard
    await expect(page.url()).toContain('/');
    await expect(page.locator('h1')).toContainText('Podcast Digest Web UI');

    // Check for dashboard-specific content
    await expect(page.locator('body')).toContainText('Dashboard');
  });

  test('Feeds tab loads correctly', async ({ page }) => {
    // Click on Feeds tab
    await page.click('a[href="/feeds"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the feeds page
    await expect(page.url()).toContain('/feeds');

    // Check for feeds-specific content (should not have error messages)
    const errorMessages = await page.locator('text=AttributeError').count();
    expect(errorMessages).toBe(0);

    // Should have feeds-related content
    await expect(page.locator('body')).toContainText('Feeds');
  });

  test('Topics tab loads correctly', async ({ page }) => {
    // Click on Topics tab
    await page.click('a[href="/topics"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the topics page
    await expect(page.url()).toContain('/topics');

    // Check for topics-specific content
    await expect(page.locator('body')).toContainText('Topics');
  });

  test('Script Lab tab loads correctly', async ({ page }) => {
    // Click on Script Lab tab
    await page.click('a[href="/script-lab"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the script lab page
    await expect(page.url()).toContain('/script-lab');

    // Check for script lab-specific content
    await expect(page.locator('body')).toContainText('Script Lab');
  });

  test('Episodes tab loads correctly', async ({ page }) => {
    // Click on Episodes tab
    await page.click('a[href="/episodes"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the episodes page
    await expect(page.url()).toContain('/episodes');

    // Check for episodes-specific content
    await expect(page.locator('body')).toContainText('Episodes');
  });

  test('Publishing tab loads correctly', async ({ page }) => {
    // Click on Publishing tab
    await page.click('a[href="/publishing"]');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the publishing page
    await expect(page.url()).toContain('/publishing');

    // Check for publishing-specific content
    await expect(page.locator('body')).toContainText('Publishing');
  });

  test('All tabs accessible sequentially', async ({ page }) => {
    const tabs = [
      { href: '/', name: 'Dashboard' },
      { href: '/feeds', name: 'Feeds' },
      { href: '/topics', name: 'Topics' },
      { href: '/script-lab', name: 'Script Lab' },
      { href: '/episodes', name: 'Episodes' },
      { href: '/publishing', name: 'Publishing' }
    ];

    // Test each tab in sequence
    for (const tab of tabs) {
      console.log(`Testing tab: ${tab.name}`);

      // Click on the tab
      await page.click(`a[href="${tab.href}"]`);

      // Wait for page to load
      await page.waitForLoadState('networkidle');

      // Verify URL
      await expect(page.url()).toContain(tab.href === '/' ? 'http://127.0.0.1:5001/' : tab.href);

      // Verify no error messages
      const errorCount = await page.locator('text=Error').count();
      const attributeErrorCount = await page.locator('text=AttributeError').count();
      const tracebackCount = await page.locator('text=Traceback').count();

      expect(errorCount + attributeErrorCount + tracebackCount).toBe(0);

      // Wait a bit between tabs
      await page.waitForTimeout(500);
    }
  });
});