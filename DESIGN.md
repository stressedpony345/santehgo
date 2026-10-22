# SantehGo UI system

This document records the current visual language of the public SantehGo site and the constraints for its gradual improvement. It describes the existing Django-template interface; it does not redefine prices, request handling, or backend behavior.

## Product principles

- Mobile-first: the main customer flow must remain usable from 320px wide screens and with a software keyboard open.
- Service-first: a visitor should be able to find a service, understand its indicative price, select work, and submit a request without losing context.
- Clear over decorative: motion and visual effects support hierarchy but must not obscure controls or content.
- Progressive enhancement: server-rendered content and native controls remain the fallback when JavaScript is unavailable.
- No frontend framework is required. Django templates, CSS, and small ES modules are the default stack.

## Current foundations

### Typography

- `Manrope`: body text, form controls, navigation, and buttons.
- `Unbounded`: display headings, service titles, and high-emphasis actions.
- `Caveat`: legacy decorative accent. It is loaded by the page but is effectively hidden by the current hero refresh and should not be used for new components.

Typography rules:

- Body text should not be smaller than `16px` on form controls to prevent iOS input zoom.
- Supporting mobile text should normally be at least `14px`.
- `Unbounded` is reserved for short text; long labels and descriptions use `Manrope`.
- Text must remain selectable except where selection would interfere with a control.

### Color roles

The stylesheet currently contains many one-off colors. The following values represent the intended roles and are the candidates for canonical tokens during CSS consolidation.

- Deep background: `#0a1a2e`.
- Hero navy: `#071e35` to `#0c355d`.
- Primary blue: `#1683d8`.
- Interactive blue: `#1a7fd4`.
- Primary text: `#0d2744`.
- Muted text: `#4a6a85`.
- Page surface: `#f7fbff`.
- Soft blue surface: `#e8f4fc`.
- White surface: `#ffffff`.
- Primary conversion action: `#ff7a1a` to `#ff9630`.
- Positive status: `#2ecb6a`.
- Error status: `#b42318`.

Any new color must be assigned a semantic role. New one-off hexadecimal values should not be added.

### Layout

- Maximum content width: `1180px`.
- Desktop page padding: `2rem`.
- Current compact/mobile page padding: between `0.4rem` and `0.75rem` per side depending on section.
- Primary card radius: `1.25rem`.
- Large hero/form radius: `1.45rem` to `1.75rem`.
- Pill radius: `999px`.
- Minimum interactive target: `44px`; primary actions should be `46–48px` or taller.

### Responsive ranges

The current CSS uses overlapping widths. During consolidation, components should use these shared ranges:

- Compact mobile: up to `380px`.
- Mobile: up to `720px`.
- Tablet: `721px` to `960px`.
- Compact desktop: `961px` to `1080px`.
- Wide: above `1080px`.

Do not introduce another breakpoint without documenting the component need here.

### Elevation and layers

Target layer scale:

- Content and decorative elements: `0–9`.
- Sticky selected-work panel: `30`.
- Dropdowns and popovers: `40`.
- Modal backdrop/dialog: `50`.
- Toasts and urgent feedback: `60`.

Popover geometry must account for `visualViewport`, `dvh`, and safe-area insets. Components must not introduce arbitrary values such as `z-index: 10000`.

## Core components

### Hero and quick quote

- The main CTA scrolls to the quick quote form.
- Service selection is a searchable combobox backed by the native `<select>`.
- Address suggestions are restricted to Chelyabinsk.
- Visit date is limited to the current 30-day booking window.
- Opening one picker closes all other pickers.
- Popovers must close on explicit selection, Escape, or outside interaction without following the page during scroll.

### Catalog search

- Search is global and includes category, service name, service description, work name, and work description.
- An empty result must keep a clear recovery path.
- Search and category selection are separate states: entering a query searches all categories.

### Category navigation

- Categories remain horizontally reachable on small screens.
- Visual order, DOM order, and keyboard order must match.
- The active category is represented in text/color and with `aria-pressed`.
- Scroll position must be visible and operable with touch, pointer, and keyboard.

### Service card and work selection

- Each card exposes the service, description, indicative price, and selected-work count.
- The explicit action button is the canonical activation target.
- Work selections inside the modal are staged until the user saves them.
- Closing without saving must leave the previously saved selection unchanged.

### Selected-work panel

- The panel appears only when at least one work is selected.
- It shows count and indicative total while keeping the checkout action dominant.
- On mobile it must respect `env(safe-area-inset-bottom)` and must not cover the last catalog item.
- Count and total changes must be announced through a polite live region.

### Request modal

- The summary must reflect the exact flow used to open it: quick quote or selected catalog works.
- Submission has idle, submitting, error, and success states.
- Errors are announced and focus moves to the message when appropriate.
- Successful submission redirects to the existing success page.

## Overlay accessibility contract

Every modal, combobox, picker, and suggestion list must follow a shared lifecycle:

1. Record the invoking element.
2. Close incompatible overlays.
3. Open within the visible viewport.
4. Move focus to a meaningful first control for modal dialogs.
5. Keep modal focus inside the dialog and make the background inert.
6. Support Escape where dismissal is allowed.
7. Restore focus to the invoking element.

Comboboxes must expose an accessible name, `aria-expanded`, `aria-controls`, active option state, and complete Arrow/Home/End/Enter/Escape behavior.

## Motion

- Motion should explain state changes and normally remain between `150ms` and `360ms`.
- `prefers-reduced-motion: reduce` disables decorative animation and replaces smooth programmatic scrolling with immediate movement.
- Visual regression tests run with reduced motion enabled.

## Quality gates

A component change is complete when:

- its keyboard flow is covered by Playwright;
- mobile Chromium and mobile WebKit scenarios pass;
- it has no critical or serious accessibility violations;
- relevant screenshots were reviewed intentionally;
- no horizontal page overflow occurs at the supported widths;
- business payloads and backend behavior remain unchanged unless separately approved.

## Visual regression matrix

Required representative viewports:

- Desktop Chromium: `1440×900`.
- Tablet: `768×1024`.
- Mobile Chromium: Pixel-class viewport.
- Mobile WebKit: iPhone-class viewport.
- Narrow layout check: `320px` wide.

Stable screenshots cover the hero and quick quote, service picker, address suggestions, calendar, category navigation, catalog search/empty states, work-selection modal, selected-work panel, and request modal.

Current baselines are generated on Windows and are intended for developer review. Browser font rasterization differs by operating system, so screenshot comparison must become a required CI check only after the fonts are self-hosted and the approved baselines are regenerated in a pinned Linux container. Normal CI must never update snapshots automatically.

## Implementation sequence

### Phase 1: quality baseline — complete

- Record the existing visual system and interaction contracts in this document.
- Run Django with an isolated deterministic E2E database and fixture.
- Cover Chromium, Firefox, mobile Chromium, and mobile WebKit with Playwright.
- Add critical/serious accessibility scans and stable component screenshots.
- Run browser and accessibility checks for pull requests without changing the production deploy workflow.

### Phase 2: CSS consolidation

- Extract semantic color, spacing, radius, shadow, typography, and layer variables at the top of `static/core/css/home.css`.
- Merge repeated `.hero__max-link` rules and overlapping mobile media queries in `static/core/css/home.css` without changing the rendered layout.
- Map every existing `z-index` to the documented layer scale.
- Keep the current HTML class contract so templates and JavaScript continue to work.

### Phase 3: overlay controller

- Consolidate the service combobox, address suggestions, and visit picker lifecycle currently implemented in `static/core/js/services.js`.
- Share close-on-scroll, viewport positioning, focus restoration, Escape handling, and mobile keyboard behavior.
- Preserve the existing form field names, request payloads, and API endpoints.

### Phase 4: catalog navigation and discovery

- Simplify category-scroll state in `static/core/js/services.js` and its visual rules in `static/core/css/home.css`.
- Verify global search, keyboard category navigation, empty results, and 320px layouts.
- Keep category, service, work, description, and price data unchanged.

### Phase 5: selection and checkout flow

- Unify focus trapping and announcements for the work-selection and request dialogs in `static/core/js/services.js`.
- Reduce visual competition between the sticky selected-work panel and catalog content in `static/core/css/home.css`.
- Verify that staged selections, totals, and request summaries remain identical to the current backend contract.

### Phase 6: performance and CI visual gate

- Self-host the current Manrope and Unbounded font files to remove render-blocking third-party font requests and make screenshots deterministic.
- Measure static asset weight and split only proven critical/non-critical CSS or JavaScript boundaries.
- Generate and approve Linux baselines in a pinned environment, then enable `pnpm run test:visual` as a required CI job.

## UX improvement backlog

1. **One overlay lifecycle.** The service list, address suggestions, and calendar independently calculate geometry and dismissal in `static/core/js/services.js`. A shared controller will prevent scroll, focus, and software-keyboard fixes from diverging.
2. **One responsive vocabulary.** `static/core/css/home.css` contains overlapping width rules and repeated selector overrides. Consolidating them around the five documented ranges will make mobile behavior predictable.
3. **Stable typography.** `core/templates/core/home.html` currently depends on externally hosted fonts. Self-hosting preserves the identity while improving first render and visual-test consistency.
4. **Explicit modal semantics.** The work and request dialogs in `core/templates/core/home.html` should use one focus/announcement contract, verified by `tests/e2e/specs/catalog.spec.ts` and `tests/e2e/specs/accessibility.spec.ts`.
5. **Visible catalog position.** Category scrolling in `static/core/js/services.js` and `static/core/css/home.css` should keep the active category and scrollbar state synchronized for touch, pointer, and keyboard users.
6. **Safe sticky panel spacing.** The selected-work panel must reserve its own page space at every mobile width, including safe-area insets, so the final service card remains reachable.
7. **Consistent empty and error states.** Catalog search, address lookup, and request submission should use the same tone, spacing, and recovery-action pattern without changing their backend behavior.
