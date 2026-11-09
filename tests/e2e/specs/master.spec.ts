import { expect, test } from '../fixtures/playwright';

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (error) => console.error(`MASTER_PAGE_ERROR: ${error.message}`));
  await page.goto('/masters/login/');
  await page.getByRole('textbox', { name: 'Логин' }).fill('e2e-master');
  await page.getByRole('textbox', { name: 'Пароль' }).fill('E2e-master-pass-2026');
  await page.getByRole('button', { name: /Войти/ }).click();
  await expect(page).toHaveURL(/\/masters\/$/);
  await expect(page.getByRole('heading', { name: /Новые заявки/ })).toBeVisible();
});

test('черновик отчёта и выбранные файлы переживают закрытие и сетевую ошибку', async ({ page }) => {
  await expect(page.locator('#mine-count')).toHaveText('1');
  await page.getByRole('button', { name: 'Мои' }).click();
  await page.getByRole('button', { name: 'Сдать отчёт' }).click();
  const dialog = page.getByRole('dialog', { name: 'Отправить работу на проверку' });
  const comment = dialog.getByRole('textbox', { name: 'Комментарий модератору' });
  await comment.fill('Проверено давление и герметичность соединений');
  await dialog.locator('input[name="photos"]').setInputFiles({
    name: 'result.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
  });
  await expect(dialog.getByText('result.jpg')).toBeVisible();

  await dialog.getByRole('button', { name: 'Закрыть' }).click();
  await page.getByRole('button', { name: 'Сдать отчёт' }).click();
  await expect(comment).toHaveValue('Проверено давление и герметичность соединений');
  await expect(dialog.getByText('result.jpg')).toBeVisible();

  await page.route('**/masters/api/requests/*/complete/', (route) => route.abort());
  page.once('dialog', (confirmation) => confirmation.accept());
  await dialog.getByRole('button', { name: 'Отправить на проверку' }).click();
  await expect(dialog).toBeVisible();
  await expect(comment).toHaveValue('Проверено давление и герметичность соединений');
  await expect(dialog.getByText('result.jpg')).toBeVisible();
  await expect(dialog.getByRole('progressbar')).toBeVisible();

  await dialog.getByRole('button', { name: 'Удалить result.jpg' }).click();
  await expect(dialog.getByText('result.jpg')).toBeHidden();
});

test('поиск общей очереди фильтрует заявки без открытия карточек', async ({ page }) => {
  const search = page.getByRole('searchbox', { name: 'Поиск по общей очереди' });
  await expect(page.locator('#available-list').getByRole('heading', { name: 'Течёт смеситель на кухне' })).toBeVisible();
  await expect(page.locator('#available-list').getByRole('heading', { name: 'Установить стиральную машину' })).toBeVisible();
  await search.fill('стиральную');
  await expect(page.locator('#available-list .request-card')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Установить стиральную машину' })).toBeVisible();
  await search.fill('несуществующая работа');
  await expect(page.locator('#available-list .request-card')).toHaveCount(0);
  await expect(page.locator('#available-empty')).toBeVisible();
});

test('мобильный кабинет не прокручивается по горизонтали и основные зоны не меньше 44 px', async ({ page }) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  const tooSmall = await page.locator('button:visible, a.detail-phone:visible').evaluateAll((elements) =>
    elements
      .map((element) => ({
        label: element.getAttribute('aria-label') || element.textContent?.trim() || element.tagName,
        width: element.getBoundingClientRect().width,
        height: element.getBoundingClientRect().height,
      }))
      .filter((item) => item.width < 44 || item.height < 44),
  );
  expect(tooSmall).toEqual([]);
});
