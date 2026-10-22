import { expect, test } from '../fixtures/playwright';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('главная не создаёт горизонтальную прокрутку', async ({ page }) => {
  await expect(page.getByRole('heading', { level: 1 })).toContainText('САНТЕХНИК РЯДОМ');
  await expect(page.locator('#quote-form')).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('CTA переводит пользователя к быстрому расчёту', async ({ page }) => {
  await page.getByRole('link', { name: 'Рассчитать стоимость' }).click();
  await expect(page.locator('#quote-form')).toBeInViewport();
});

test('услугу можно найти, выбрать и сбросить', async ({ page }) => {
  const serviceSearch = page.locator('.select__search');
  await serviceSearch.focus();
  await expect(page.locator('.select__menu--search')).toBeVisible();
  await expect(page.locator('.select__menu--search .select__option:visible')).toHaveCount(7);

  await serviceSearch.fill('смеситель');
  await expect(page.locator('.select__menu--search .select__option:visible')).toHaveCount(1);
  await page.getByRole('option', { name: 'Кухонный смеситель' }).click();
  await expect(serviceSearch).toHaveValue('Кухонный смеситель');

  await page.getByRole('button', { name: 'Очистить выбранную услугу' }).click();
  await expect(serviceSearch).toHaveValue('');
  await expect(page.locator('.select__menu--search .select__option:visible')).toHaveCount(7);
});

test('плавающие списки открываются по одному и закрываются через Escape', async ({ page }) => {
  const serviceSearch = page.locator('.select__search');
  await serviceSearch.focus();
  await expect(page.locator('.select__menu--search')).toBeVisible();

  const visitToggle = page.getByRole('button', { name: 'Выберите дату и время' });
  await visitToggle.click();
  await expect(page.locator('.select__menu--search')).toBeHidden();
  await expect(page.getByRole('dialog', { name: 'Дата и время выезда мастера' })).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Дата и время выезда мастера' })).toBeHidden();
  await expect(visitToggle).toBeFocused();
});

test('адрес и время выбираются в быстром расчёте', async ({ page }) => {
  await page.route('**/api/address-suggestions/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        suggestions: [
          {
            value: 'г. Челябинск, Вишнёвая аллея, д. 19',
            title: 'Вишнёвая аллея, 19',
            subtitle: 'Челябинск',
          },
          {
            value: 'г. Челябинск, Вишнёвая аллея, д. 19А',
            title: 'Вишнёвая аллея, 19А',
            subtitle: 'Челябинск',
          },
        ],
      }),
    });
  });

  const address = page.getByRole('combobox', { name: 'Ваш адрес' });
  await address.fill('Вишнёвая аллея 19');
  await expect(page.getByRole('option', { name: /Вишнёвая аллея, 19 Челябинск/ })).toBeVisible();
  await address.press('ArrowDown');
  await address.press('Enter');
  await expect(address).toHaveValue('г. Челябинск, Вишнёвая аллея, д. 19');

  await page.getByRole('button', { name: 'Выберите дату и время' }).click();
  const visitDialog = page.getByRole('dialog', { name: 'Дата и время выезда мастера' });
  await expect(visitDialog).toBeVisible();
  await visitDialog.getByRole('button', { name: 'Сегодня' }).click();
  await visitDialog.getByRole('button', { name: '09:00–12:00' }).click();
  await expect(page.locator('#visit-toggle')).toContainText('Сегодня, 09:00–12:00');
});
