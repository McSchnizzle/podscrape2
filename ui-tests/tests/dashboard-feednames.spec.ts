import { test, expect } from '@playwright/test';

test.describe('Dashboard feed names for undigested episodes', () => {
  test('undigested list shows feed titles not all identical', async ({ page }) => {
    await page.goto('/');
    const section = page.locator('h3', { hasText: 'Transcribed Not Yet Digested' }).locator('xpath=..');
    const items = section.locator('ul li');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'No undigested episodes to validate');
      return;
    }
    const texts: string[] = [];
    for (let i = 0; i < Math.min(count, 10); i++) {
      texts.push(await items.nth(i).innerText());
    }
    // Extract feed names after the dash —  (em dash or hyphen)
    const feeds = texts.map(t => {
      const m = t.split('—')[1] || t.split('-')[1];
      return m ? m.split('(status')[0].trim() : '';
    }).filter(Boolean);
    const unique = new Set(feeds);
    // Expect at least 2 unique feed names when there are 3+ items; otherwise allow 1
    if (feeds.length >= 3) {
      expect(unique.size).toBeGreaterThan(1);
    } else {
      expect(feeds.length).toBeGreaterThan(0);
    }
  });
});

