import { test, expect } from '@playwright/test';

test.describe('Pipeline run via dashboard', () => {
  test('starts full pipeline, streams log lines', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Accept confirmation dialog triggered by form onsubmit
    page.once('dialog', d => d.accept());

    await page.getByRole('button', { name: 'Run Full Pipeline' }).click();

    // Flash message confirms start and log filename
    await expect(page.locator('text=Started full pipeline. Logging to')).toBeVisible();

    // Live Status should auto-start and show Stop button
    await expect(page.getByRole('button', { name: 'Stop' })).toBeVisible();

    // Live log should receive content soon (from initial tail or early output)
    const liveLog = page.getByTestId('live-log');
    await expect(liveLog).toBeVisible();

    // Wait for any indicative text to appear
    await expect(liveLog).toContainText(/Launching:|Verifying pipeline|Traceback|FULL RSS PODCAST PIPELINE/i, { timeout: 15000 });

    // Copy the log to clipboard and verify it has content
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    const copyBtn = page.getByTestId('copy-log');
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    const clip = await page.evaluate(async () => navigator.clipboard.readText());
    expect(clip.length).toBeGreaterThan(0);

    // Clear the log and verify it empties
    const clearBtn = page.getByTestId('clear-log');
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();
    await expect(liveLog).toHaveText('');
  });
});
