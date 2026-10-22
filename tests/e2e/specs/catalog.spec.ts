import { expect, test } from '../fixtures/playwright';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.locator('#content').scrollIntoViewIfNeeded();
});

test('глобальный поиск учитывает названия и описания работ', async ({ page }) => {
  const search = page.getByRole('searchbox', { name: 'Что нужно сделать?' });
  await search.fill('влажных зон');

  await expect(page.locator('.service-card')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Диагностика протечки' })).toBeVisible();
  await expect(page.locator('#catalog-count')).toHaveText('1 услуга');
});

test('категория фильтрует каталог', async ({ page }) => {
  const category = page.getByRole('button', { name: 'Кухня', exact: true });
  await category.focus();
  await category.press('Enter');
  await expect(category).toHaveAttribute('aria-pressed', 'true');
  await expect(category).toBeFocused();
  await expect(page.locator('.service-card')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Кухонный смеситель' })).toBeVisible();
});

test('категории доступны с клавиатуры, а прокрутка показывает положение', async ({ page }) => {
  const scrollbar = page.locator('#category-scroll');
  const categoryNav = page.locator('#category-nav');
  const needsScroll = await categoryNav.evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  if (!needsScroll) {
    await expect(scrollbar).toBeHidden();
    return;
  }
  await expect(scrollbar).toBeVisible();
  await scrollbar.focus();
  await scrollbar.press('End');
  await expect.poll(async () => Number(await scrollbar.getAttribute('aria-valuenow'))).toBeGreaterThan(90);
  await scrollbar.press('Home');
  await expect.poll(async () => Number(await scrollbar.getAttribute('aria-valuenow'))).toBeLessThan(10);
});

test('несколько работ сохраняются и попадают в оформление', async ({ page }) => {
  const diagnosticsCard = page.locator('.service-card').filter({ hasText: 'Диагностика протечки' });
  await diagnosticsCard.getByRole('button', { name: 'Выбрать работы' }).click();

  const worksDialog = page.getByRole('dialog', { name: 'Диагностика протечки' });
  await expect(worksDialog).toBeVisible();
  await worksDialog.getByRole('checkbox', { name: /Поиск скрытой протечки/ }).check();
  await worksDialog.getByRole('checkbox', { name: /Проверка давления/ }).check();
  await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();

  const selectedPanel = page.locator('#work-list');
  await expect(selectedPanel).toBeVisible();
  await expect(selectedPanel).toContainText('2 работы');
  await expect(selectedPanel).toContainText('2 400 ₽');

  await selectedPanel.getByRole('button', { name: 'Оставить заявку' }).click();
  const requestDialog = page.getByRole('dialog', { name: 'Контактные данные' });
  await expect(requestDialog).toBeVisible();
  await expect(requestDialog).toContainText('Поиск скрытой протечки');
  await expect(requestDialog).toContainText('Проверка давления');
});

test('отмена выбора не сохраняет работу и возвращает фокус', async ({ page }) => {
  const card = page.locator('.service-card').filter({ hasText: 'Диагностика протечки' });
  const trigger = card.getByRole('button', { name: 'Выбрать работы' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Диагностика протечки' });
  await expect(dialog.getByRole('button', { name: 'Закрыть' })).toBeFocused();
  await dialog.getByRole('checkbox', { name: /Поиск скрытой протечки/ }).check();
  await dialog.getByRole('button', { name: 'Закрыть' }).click();
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await expect(page.locator('#work-list')).toBeHidden();
});

test('фокус остаётся внутри модального окна', async ({ page }) => {
  const card = page.locator('.service-card').filter({ hasText: 'Диагностика протечки' });
  await card.getByRole('button', { name: 'Выбрать работы' }).click();
  const dialog = page.getByRole('dialog', { name: 'Диагностика протечки' });
  await dialog.getByRole('button', { name: 'Сохранить выбор' }).focus();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Закрыть' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Сохранить выбор' })).toBeFocused();
});

test('очистка скрывает панель выбранных работ', async ({ page }) => {
  const diagnosticsCard = page.locator('.service-card').filter({ hasText: 'Диагностика протечки' });
  await diagnosticsCard.getByRole('button', { name: 'Выбрать работы' }).click();
  const worksDialog = page.getByRole('dialog', { name: 'Диагностика протечки' });
  await worksDialog.getByRole('checkbox', { name: /Поиск скрытой протечки/ }).check();
  await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();

  await page.locator('#work-list').getByRole('button', { name: 'Очистить' }).click();
  await expect(page.locator('#work-list')).toBeHidden();
});
