import { expect, test as base } from '@playwright/test';


const externalFontRequest = /^https:\/\/fonts\.(?:googleapis|gstatic)\.com\//;

export const test = base.extend({
  context: async ({ context }, use) => {
    await context.route(externalFontRequest, (route) => route.abort());
    await use(context);
  },
});

export { expect };
