import { test, expect } from '@playwright/test';

// Functional test: add a customer, start a run, verify run appears
// Prereqs: Backend running at 127.0.0.1:8000 and Frontend Vite at localhost:5173

test.describe('AI Cost Tracker flows', () => {
  test('Add customer, start run, list runs', async ({ page }) => {
    await page.goto('/');

    // Add customer
    await page.getByPlaceholder('Name').fill('E2E User');
    await page.getByPlaceholder('Email (optional)').fill('e2e@example.com');
    await page.getByRole('button', { name: 'Add' }).click();

    // Should appear in Customers list as a selectable button
    const customerButton = page.getByRole('button', { name: /E2E User/ }).first();
    await expect(customerButton).toBeVisible();

    // Select the customer (list item is a button)
    await customerButton.click();

    // Start a run with default prompt
    await page.getByRole('button', { name: 'Start' }).click();

    // Give backend some time to update, then refresh runs
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: 'Refresh Runs' }).click();

    // Expect at least one run row to be visible
    const firstRow = page.locator('table.runs tbody tr').first();
    await expect(firstRow).toBeVisible();
    // Expect row to have at least 4 cells (ID, Provider, Model, Success)
    const cellCount = await firstRow.locator('td').count();
    expect(cellCount).toBeGreaterThanOrEqual(4);
  });
});
