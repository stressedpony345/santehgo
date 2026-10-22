import AxeBuilder from '@axe-core/playwright';

import { expect, test } from '../fixtures/playwright';


async function expectNoSeriousViolations(page) {
  await expect(page.locator('.select--searchable')).toBeVisible();
  await expect(page.locator('.service-card')).toHaveCount(7);

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  const violations = results.violations
    .filter(({ impact }) => impact === 'critical' || impact === 'serious')
    .map(({ id, impact, help, nodes }) => ({
      id,
      impact,
      help,
      targets: nodes.map((node) => node.target.join(' ')),
    }));

  expect(violations).toEqual([]);
}

test('главная страница не содержит серьёзных a11y-нарушений', async ({ page }) => {
  await page.goto('/');
  await expectNoSeriousViolations(page);
});

test('модальное окно работ не содержит серьёзных a11y-нарушений', async ({ page }) => {
  await page.goto('/');
  await page.locator('.service-card').filter({ hasText: 'Диагностика протечки' })
    .getByRole('button', { name: 'Выбрать работы' })
    .click();
  await expect(page.getByRole('dialog', { name: 'Диагностика протечки' })).toBeVisible();
  await expectNoSeriousViolations(page);
});
