import { expect, test } from '../fixtures/playwright';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.locator('#content').scrollIntoViewIfNeeded();
});

test('выбор категории отправляет только обезличенный код начала каталога', async ({ page }) => {
  const events: unknown[] = [];
  await page.route('**/api/product-events/', async (route) => {
    events.push(route.request().postDataJSON());
    await route.fulfill({ status: 204 });
  });

  await page.getByRole('button', { name: 'Кухня', exact: true }).click();

  await expect.poll(() => events).toEqual([{ event: 'catalog_started' }]);
});

test('поиск в каталоге отправляет одно событие без поискового текста', async ({ page }) => {
  const events: unknown[] = [];
  await page.route('**/api/product-events/', async (route) => {
    events.push(route.request().postDataJSON());
    await route.fulfill({ status: 204 });
  });

  await page.getByRole('searchbox', { name: 'Что нужно сделать?' }).fill('личная проблема клиента');

  await expect.poll(() => events).toEqual([{ event: 'catalog_started' }]);
});

test('выбор работы без фильтра тоже учитывает начало каталога', async ({ page }) => {
  const events: unknown[] = [];
  await page.route('**/api/product-events/', async (route) => {
    events.push(route.request().postDataJSON());
    await route.fulfill({ status: 204 });
  });

  await page.locator('.service-card').first().getByRole('button', { name: 'Выбрать работы' }).click();

  await expect.poll(() => events).toEqual([{ event: 'catalog_started' }]);
});

test('контакты из каталога учитываются один раз без состава заявки', async ({ page }) => {
  const events: unknown[] = [];
  await page.route('**/api/product-events/', async (route) => {
    events.push(route.request().postDataJSON());
    await route.fulfill({ status: 204 });
  });

  await page.locator('.service-card').first().getByRole('button', { name: 'Выбрать работы' }).click();
  const worksDialog = page.getByRole('dialog').filter({ has: page.locator('#services-form') });
  await worksDialog.getByRole('checkbox').first().check();
  await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();
  await page.locator('#work-list').getByRole('button', { name: 'Оставить заявку' }).click();

  await expect.poll(() => events).toEqual([{ event: 'catalog_started' }, { event: 'contacts_opened' }]);
});

test('поиск сбрасывает выбранную категорию, чтобы фильтры не противоречили результатам', async ({ page }) => {
  const category = page.getByRole('button', { name: 'Кухня', exact: true });
  await category.click();
  await expect(category).toHaveAttribute('aria-pressed', 'true');

  await page.getByRole('searchbox', { name: 'Что нужно сделать?' }).fill('протечка');

  await expect(page.getByRole('button', { name: 'Все категории' })).toHaveAttribute('aria-pressed', 'true');
  await expect(category).toHaveAttribute('aria-pressed', 'false');
});

test('пустой результат предлагает сбросить поиск и возвращает каталог', async ({ page }) => {
  const search = page.getByRole('searchbox', { name: 'Что нужно сделать?' });
  await search.fill('несуществующая услуга');
  await expect(page.locator('#categories-empty')).toBeVisible();

  await page.locator('#categories-empty').getByRole('button', { name: 'Сбросить фильтры' }).click();

  await expect(search).toHaveValue('');
  await expect(page.locator('.service-card')).toHaveCount(7);
});

test('выбор категории после поиска показывает именно выбранный раздел', async ({ page }) => {
  const search = page.getByRole('searchbox', { name: 'Что нужно сделать?' });
  await search.fill('протечка');
  await page.getByRole('button', { name: 'Кухня', exact: true }).click();

  await expect(search).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Кухня', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.service-card')).toHaveCount(1);
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

test('повтор отправки после сетевой ошибки сохраняет данные и ключ заявки', async ({ page }) => {
  async function fillSameRequest() {
    const card = page.locator('.service-card').first();
    await card.getByRole('button', { name: 'Выбрать работы' }).click();
    const worksDialog = page.getByRole('dialog').filter({ has: page.locator('#services-form') });
    await worksDialog.getByRole('checkbox').first().check();
    await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();
    await page.locator('#work-list').getByRole('button', { name: 'Оставить заявку' }).click();

    const form = page.locator('#contacts-form');
    await form.locator('[name="full_name"]').fill('Иван Иванов');
    await form.locator('[name="phone"]').fill('+7 999 123-45-67');
    await form.locator('[name="consent"]').check();
    return form;
  }

  const keys: string[] = [];
  let attempt = 0;
  let createdRequestUrl = '';
  await page.route('**/api/requests/', async (route) => {
    keys.push(await route.request().headerValue('idempotency-key') || '');
    attempt += 1;
    if (attempt === 1) {
      const serverResponse = await route.fetch();
      const result = await serverResponse.json();
      createdRequestUrl = result.success_url;
      await route.abort('failed');
      return;
    }
    await route.continue();
  });

  let form = await fillSameRequest();
  await form.getByRole('button', { name: 'Отправить заявку' }).click();

  await expect(page.locator('#contacts-error')).toBeVisible();
  await expect(form.locator('[name="full_name"]')).toHaveValue('Иван Иванов');
  await expect(form).not.toHaveAttribute('aria-busy');
  await expect(form.getByRole('button', { name: 'Отправить заявку' })).toBeEnabled();
  expect(createdRequestUrl).toMatch(/^\/request\/[0-9a-f-]+\/$/);

  await page.reload();
  await expect(page).toHaveURL(new RegExp(`${createdRequestUrl.replaceAll('/', '\\/')}$`));

  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe('');
  expect(keys[1]).toBe(keys[0]);
});

test('изменённая заявка после ошибки получает новый ключ отправки', async ({ page }) => {
  const card = page.locator('.service-card').first();
  await card.getByRole('button', { name: 'Выбрать работы' }).click();
  const worksDialog = page.getByRole('dialog').filter({ has: page.locator('#services-form') });
  await worksDialog.getByRole('checkbox').first().check();
  await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();
  await page.locator('#work-list').getByRole('button', { name: 'Оставить заявку' }).click();

  const keys: string[] = [];
  await page.route('**/api/requests/', async (route) => {
    keys.push(await route.request().headerValue('idempotency-key') || '');
    await route.fulfill({
      status: keys.length === 1 ? 503 : 200,
      contentType: 'application/json',
      body: JSON.stringify(keys.length === 1
        ? { ok: false, error: 'Временная ошибка' }
        : { ok: true, success_url: '/request-success/' }),
    });
  });

  const form = page.locator('#contacts-form');
  await form.locator('[name="full_name"]').fill('Иван Иванов');
  await form.locator('[name="phone"]').fill('+7 999 123-45-67');
  await form.locator('[name="consent"]').check();
  await form.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page.locator('#contacts-error')).toBeVisible();

  await form.locator('[name="phone"]').fill('+7 999 765-43-21');
  await form.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page).toHaveURL(/request-success/);

  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe('');
  expect(keys[1]).not.toBe(keys[0]);
});

test('путь заявки и страница статуса помещаются на ширине 320 пикселей', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  const card = page.locator('.service-card').first();
  await card.getByRole('button', { name: 'Выбрать работы' }).click();
  const worksDialog = page.getByRole('dialog').filter({ has: page.locator('#services-form') });
  await worksDialog.getByRole('checkbox').first().check();
  await worksDialog.getByRole('button', { name: 'Сохранить выбор' }).click();
  await page.locator('#work-list').getByRole('button', { name: 'Оставить заявку' }).click();

  const form = page.locator('#contacts-form');
  await form.locator('[name="full_name"]').fill('Мобильный клиент');
  await form.locator('[name="phone"]').fill('+7 999 123-45-67');
  await form.locator('[name="consent"]').check();
  await form.getByRole('button', { name: 'Отправить заявку' }).click();

  await expect(page).toHaveURL(/\/request\/[0-9a-f-]+\/$/);
  await expect(page.getByRole('button', { name: 'Перезвоните мне' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Запросить отмену' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('согласие ведёт на читаемый версионированный документ', async ({ page }) => {
  const consentLink = page.locator('.contacts__consent a');
  await expect(consentLink).toHaveAttribute('href', '/personal-data-consent/');
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto(await consentLink.getAttribute('href') || '/personal-data-consent/');

  await expect(page.getByRole('heading', { name: 'Согласие на обработку персональных данных' })).toBeVisible();
  await expect(page.getByText('Тестовый оператор САНТЕХГО', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Версия e2e-1', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
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
