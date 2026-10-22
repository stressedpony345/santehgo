import { expect, test } from '../fixtures/playwright';

test('@visual главная и быстрый расчёт', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator('.hero')).toHaveScreenshot('hero-and-quote.png');
});

test('@visual каталог и категории', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  await page.locator('#content').scrollIntoViewIfNeeded();
  await expect(page.locator('.services')).toHaveScreenshot('catalog.png');
});

test('@visual выбор работ и плавающая панель', async ({ page }) => {
  await page.goto('/');
  await page.locator('#content').scrollIntoViewIfNeeded();
  const card = page.locator('.service-card').filter({ hasText: 'Диагностика протечки' });
  await card.getByRole('button', { name: 'Выбрать работы' }).click();
  const dialog = page.getByRole('dialog', { name: 'Диагностика протечки' });
  await expect(dialog).toHaveScreenshot('work-selection-modal.png');
  await dialog.getByRole('checkbox', { name: /Поиск скрытой протечки/ }).check();
  await dialog.getByRole('button', { name: 'Сохранить выбор' }).click();
  await expect(page.locator('#work-list')).toHaveScreenshot('selected-work-panel.png');
});
