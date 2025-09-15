import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Topics management', () => {
  test('edit fields, validate instruction files, upload', async ({ page }) => {
    await page.goto('/topics');
    await expect(page.getByRole('heading', { name: 'Topics' })).toBeVisible();

    // Grab first row inputs
    const firstRow = page.locator('tbody tr').first();
    const nameInput = firstRow.locator('input[name="name"]').first();
    const voiceInput = firstRow.locator('input[name="voice_id"]').first();
    const instrInput = firstRow.locator('input[name="instruction_file"]').first();
    const descInput = firstRow.locator('textarea[name="description"]').first();

    const origName = await nameInput.inputValue();
    // Update voice and description
    await voiceInput.fill('TEST_VOICE');
    await descInput.fill('Updated via UI test');
    // Force invalid instruction ref
    await instrInput.fill('does-not-exist-1234.md');

    // Save -> expect error
    await Promise.all([
      page.waitForURL('**/topics'),
      page.click('button:has-text("Save Topics")')
    ]);
    await expect(page.locator('text:has("instruction file not found")')).toBeVisible();

    // Upload a real file and save
    const tmpFile = path.resolve(process.cwd(), 'tests', 'tmp_instruction.md');
    fs.writeFileSync(tmpFile, '# Temporary Instructions');
    const uploadInput = firstRow.locator('input[type="file"]').first();
    await uploadInput.setInputFiles(tmpFile);

    await Promise.all([
      page.waitForURL('**/topics'),
      page.click('button:has-text("Save Topics")')
    ]);
    await expect(page.locator('text=Topics saved')).toBeVisible();

    // Reload and verify persisted values
    await page.goto('/topics');
    const voiceVal = await voiceInput.inputValue();
    const descVal = await descInput.inputValue();
    const instrVal = await instrInput.inputValue();
    expect(voiceVal).toBe('TEST_VOICE');
    expect(descVal).toBe('Updated via UI test');
    expect(instrVal).toBe('tmp_instruction.md');
  });
});

