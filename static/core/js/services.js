(() => {
  const dataNode = document.getElementById('categories-data');
  const track = document.getElementById('categories-track');
  const emptyState = document.getElementById('categories-empty');
  const searchInput = document.getElementById('service-search');
  const modalServices = document.getElementById('modal-services');
  const modalContacts = document.getElementById('modal-contacts');
  const checklist = document.getElementById('services-checklist');
  const servicesForm = document.getElementById('services-form');
  const contactsForm = document.getElementById('contacts-form');
  const servicesError = document.getElementById('services-error');
  const contactsError = document.getElementById('contacts-error');
  const servicesTitle = document.getElementById('modal-services-title');
  const servicesSubtitle = document.getElementById('modal-services-subtitle');
  const toast = document.getElementById('toast');
  const categoryNav = document.getElementById('category-nav');
  const categoryScroll = document.getElementById('category-scroll');
  const categoryScrollThumb = document.getElementById('category-scroll-thumb');
  const catalogCount = document.getElementById('catalog-count');
  const worksEmpty = document.getElementById('works-empty');
  const servicesSection = document.querySelector('.services');
  const workList = document.getElementById('work-list');
  const workListDetails = document.getElementById('work-list-details');
  const workListClear = document.getElementById('work-list-clear');
  const workListSubmit = document.getElementById('work-list-submit');
  const requestSummary = document.getElementById('request-summary');
  let isCategoryScrollDragging = false;
  let categoryPointerStartX = 0;
  let categoryScrollAnimation = 0;

  if (!dataNode || !track || !searchInput) return;

  let categories = [];
  try {
    categories = JSON.parse(dataNode.textContent || '[]');
  } catch (error) {
    categories = [];
  }

  const quoteForm = document.getElementById('quote-form');
  const quoteIssue = document.getElementById('quote-issue');
  let quoteDraft = {
    issue: '',
    address: '',
    preferred_time: '',
    subcategory_ids: [],
    work_ids: [],
  };
  let openSelect = null;
  let addressOverlay = null;
  let visitOverlay = null;
  let activeFloatingOverlay = null;
  const floatingOverlayGracePeriod = 350;

  function closeFloatingOverlay(overlay, { restoreFocus = false } = {}) {
    if (!overlay || !overlay.isOpen()) return;
    overlay.close();
    if (activeFloatingOverlay === overlay) activeFloatingOverlay = null;
    if (restoreFocus) overlay.invoker?.focus();
  }

  function openFloatingOverlay(overlay) {
    if (!overlay) return;
    if (activeFloatingOverlay && activeFloatingOverlay !== overlay) {
      closeFloatingOverlay(activeFloatingOverlay);
    }
    overlay.open();
    overlay.openedAt = Date.now();
    activeFloatingOverlay = overlay;
    window.requestAnimationFrame(() => overlay.position());
  }

  function isFloatingOverlayTarget(overlay, target) {
    return Boolean(overlay && target instanceof Node && overlay.contains(target));
  }

  function positionFloatingMenu({
    anchor,
    menu,
    maxHeight,
    minWidth = 0,
    maxWidth = Number.POSITIVE_INFINITY,
    preferredHeight = 180,
  }) {
    if (!anchor || !menu) return;
    const viewport = window.visualViewport;
    const viewportTop = viewport?.offsetTop || 0;
    const viewportHeight = viewport?.height || window.innerHeight;
    const viewportBottom = viewportTop + viewportHeight;
    const rect = anchor.getBoundingClientRect();
    const margin = 12;
    const gap = 8;
    const spaceBelow = viewportBottom - rect.bottom - gap - margin;
    const spaceAbove = rect.top - viewportTop - gap - margin;
    const openAbove = spaceBelow < preferredHeight && spaceAbove > spaceBelow;
    const available = Math.max(120, openAbove ? spaceAbove : spaceBelow);
    const viewportWidth = window.innerWidth - margin * 2;
    const width = Math.min(Math.max(rect.width, minWidth), maxWidth, viewportWidth);
    const left = Math.min(Math.max(margin, rect.left), window.innerWidth - margin - width);

    menu.style.left = `${left}px`;
    menu.style.width = `${width}px`;
    menu.style.maxHeight = `${Math.min(maxHeight, available)}px`;
    if (openAbove) {
      menu.style.top = 'auto';
      menu.style.bottom = `${Math.max(margin, window.innerHeight - rect.top + gap)}px`;
    } else {
      menu.style.bottom = 'auto';
      menu.style.top = `${Math.max(viewportTop + margin, rect.bottom + gap)}px`;
    }
  }

  function closeSelect(widget) {
    if (!widget) return;
    widget.classList.remove('is-open');
    widget._menu?.classList.remove('is-open');
    widget.querySelector('.select__toggle')?.setAttribute('aria-expanded', 'false');
    if (openSelect === widget) openSelect = null;
    if (activeFloatingOverlay === widget._overlay) activeFloatingOverlay = null;
  }

  function closeAllSelects() {
    closeSelect(openSelect);
  }

  function positionSelectMenu(widget) {
    const toggle = widget.querySelector('.select__toggle');
    const menu = widget._menu;
    if (!toggle || !menu) return;
    const anchor = widget.closest('.quote__field') || toggle;
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const menuHeight = Math.min(menu.scrollHeight, viewportHeight * 0.56, 288);
    positionFloatingMenu({
      anchor,
      menu,
      maxHeight: menuHeight,
      minWidth: 220,
      preferredHeight: Math.min(180, menuHeight),
    });
  }

  function syncSelectWidget(widget) {
    const select = widget.querySelector('select');
    const valueEl = widget.querySelector('.select__value');
    if (!select || !valueEl) return;

    const placeholder = select.dataset.placeholder || 'Выберите';
    const selected = [...select.options].find((option) => option.value && option.selected);
    valueEl.textContent = selected ? selected.textContent : placeholder;
    valueEl.classList.toggle('is-placeholder', !selected);

    widget._menu?.querySelectorAll('.select__option').forEach((button) => {
      button.classList.toggle('is-selected', button.dataset.value === select.value);
    });
  }

  function enhanceSelect(select) {
    if (!select || select.closest('.select')) return;

    const placeholder = select.dataset.placeholder
      || [...select.options].find((option) => !option.value)?.textContent
      || 'Выберите';

    const widget = document.createElement('div');
    widget.className = 'select';
    select.parentNode.insertBefore(widget, select);
    widget.appendChild(select);
    select.classList.add('select__native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'select__toggle';
    toggle.setAttribute('aria-haspopup', 'listbox');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.innerHTML = `
      <span class="select__value is-placeholder">${placeholder}</span>
      <svg class="select__chevron" viewBox="0 0 12 8" aria-hidden="true">
        <path d="M1 1.5 6 6.5 11 1.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
    `;

    const menu = document.createElement('div');
    menu.className = 'select__menu';
    menu.setAttribute('role', 'listbox');

    [...select.children].forEach((node) => {
      if (node.tagName === 'OPTGROUP') {
        const group = document.createElement('div');
        group.className = 'select__group';
        group.textContent = node.label;
        menu.appendChild(group);
        [...node.children].forEach((option) => {
          if (!option.value) return;
          const item = document.createElement('button');
          item.type = 'button';
          item.className = 'select__option';
          item.dataset.value = option.value;
          item.setAttribute('role', 'option');
          item.textContent = option.textContent;
          menu.appendChild(item);
        });
        return;
      }

      if (node.tagName === 'OPTION' && node.value) {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'select__option';
        item.dataset.value = node.value;
        item.setAttribute('role', 'option');
        item.textContent = node.textContent;
        menu.appendChild(item);
      }
    });

    widget.append(toggle);
    document.body.appendChild(menu);
    widget._menu = menu;

    widget._overlay = {
      invoker: toggle,
      isOpen: () => widget.classList.contains('is-open'),
      open: () => {
        widget.classList.add('is-open');
        menu.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
        openSelect = widget;
      },
      close: () => closeSelect(widget),
      position: () => positionSelectMenu(widget),
      contains: (target) => widget.contains(target) || menu.contains(target),
    };

    const open = () => {
      openFloatingOverlay(widget._overlay);
    };

    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      if (widget.classList.contains('is-open')) {
        closeSelect(widget);
      } else {
        open();
      }
    });

    menu.addEventListener('click', (event) => {
      const option = event.target.closest('.select__option');
      if (!option) return;
      select.value = option.dataset.value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      syncSelectWidget(widget);
      closeSelect(widget);
    });

    const field = widget.closest('.quote__field');
    field?.addEventListener('click', (event) => {
      if (event.target.closest('.select__toggle, .select__menu, .select__option')) return;
      if (!widget.classList.contains('is-open')) open();
    });

    syncSelectWidget(widget);
  }

  function enhanceSearchSelect(select) {
    if (!select || select.closest('.select')) return;
    const placeholder = select.dataset.placeholder || '';
    const widget = document.createElement('div');
    widget.className = 'select select--searchable';
    select.parentNode.insertBefore(widget, select);
    widget.appendChild(select);
    select.classList.add('select__native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'select__toggle select__search';
    input.placeholder = placeholder;
    input.autocomplete = 'off';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-haspopup', 'listbox');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-label', select.getAttribute('aria-label') || 'Выберите услугу');

    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'select__clear';
    clear.setAttribute('aria-label', 'Очистить выбранную услугу');
    clear.hidden = true;
    clear.innerHTML = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6 6 8 8m0-8-8 8"/></svg>';

    const menu = document.createElement('div');
    menu.className = 'select__menu select__menu--search';
    menu.setAttribute('role', 'listbox');

    [...select.children].forEach((node) => {
      if (node.tagName !== 'OPTGROUP') return;
      const group = document.createElement('div');
      group.className = 'select__group';
      group.textContent = node.label;
      menu.appendChild(group);
      [...node.children].forEach((option) => {
        if (!option.value) return;
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'select__option';
        item.dataset.value = option.value;
        item.dataset.search = normalize(`${node.label} ${option.textContent}`);
        item.setAttribute('role', 'option');
        item.textContent = option.textContent;
        menu.appendChild(item);
      });
    });

    const empty = document.createElement('p');
    empty.className = 'select__empty';
    empty.textContent = 'Ничего не найдено';
    empty.hidden = true;
    menu.appendChild(empty);
    widget.append(input, clear);
    document.body.appendChild(menu);
    widget._menu = menu;
    widget._overlay = {
      invoker: input,
      isOpen: () => widget.classList.contains('is-open'),
      open: () => {
        widget.classList.add('is-open');
        menu.classList.add('is-open');
        input.setAttribute('aria-expanded', 'true');
        openSelect = widget;
      },
      close: () => closeSelect(widget),
      position: () => positionSelectMenu(widget),
      contains: (target) => widget.contains(target) || menu.contains(target),
    };

    const filter = (queryValue = input.value) => {
      const query = normalize(queryValue);
      let visibleCount = 0;
      menu.querySelectorAll('.select__option').forEach((item) => {
        const visible = !query || item.dataset.search.includes(query);
        item.hidden = !visible;
        if (visible) visibleCount += 1;
      });
      menu.querySelectorAll('.select__group').forEach((group) => {
        let sibling = group.nextElementSibling;
        let visible = false;
        while (sibling && !sibling.classList.contains('select__group') && !sibling.classList.contains('select__empty')) {
          if (sibling.classList.contains('select__option') && !sibling.hidden) visible = true;
          sibling = sibling.nextElementSibling;
        }
        group.hidden = !visible;
      });
      empty.hidden = visibleCount > 0;
    };

    const sync = () => {
      const selected = [...select.options].find((option) => option.value && option.selected);
      input.value = selected ? selected.textContent : '';
      clear.hidden = !input.value;
      widget.classList.toggle('has-value', Boolean(input.value));
      menu.querySelectorAll('.select__option').forEach((item) => {
        item.classList.toggle('is-selected', item.dataset.value === select.value);
      });
    };
    widget._sync = sync;

    const open = ({ showAll = false } = {}) => {
      filter(showAll ? '' : input.value);
      openFloatingOverlay(widget._overlay);
    };

    input.addEventListener('focus', () => open({ showAll: true }));
    input.addEventListener('input', () => {
      select.value = '';
      widget._openedAt = Date.now();
      clear.hidden = !input.value;
      widget.classList.toggle('has-value', Boolean(input.value));
      filter();
      if (!widget.classList.contains('is-open')) open();
      positionSelectMenu(widget);
    });
    clear.addEventListener('click', (event) => {
      event.preventDefault();
      select.value = '';
      select.dispatchEvent(new Event('change', { bubbles: true }));
      input.value = '';
      clear.hidden = true;
      widget.classList.remove('has-value');
      filter('');
      input.focus();
      positionSelectMenu(widget);
    });
    input.addEventListener('keydown', (event) => {
      const visible = [...menu.querySelectorAll('.select__option:not([hidden])')];
      if (event.key === 'ArrowDown' && visible.length) {
        event.preventDefault();
        visible[0].focus();
      } else if (event.key === 'Escape') {
        closeSelect(widget);
      }
    });
    menu.addEventListener('click', (event) => {
      const option = event.target.closest('.select__option');
      if (!option) return;
      select.value = option.dataset.value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      sync();
      closeSelect(widget);
      input.blur();
    });
    sync();
  }

  document.querySelectorAll('select.quote__control').forEach((select) => {
    if (select.id === 'quote-issue') enhanceSearchSelect(select);
    else enhanceSelect(select);
  });

  const addressInput = document.getElementById('address-input');
  const addressMenu = document.getElementById('address-suggestions');
  const addressClear = document.getElementById('address-clear');
  let addressTimer = 0;
  let addressController = null;
  let addressActiveIndex = -1;
  let addressItems = [];
  if (addressMenu && addressMenu.parentElement !== document.body) document.body.appendChild(addressMenu);

  function closeAddressSuggestions() {
    if (!addressMenu || !addressInput) return;
    addressMenu.hidden = true;
    addressInput.setAttribute('aria-expanded', 'false');
    addressInput.removeAttribute('aria-activedescendant');
    addressInput.closest('.quote__field')?.classList.remove('is-expanded');
    addressActiveIndex = -1;
    if (activeFloatingOverlay === addressOverlay) activeFloatingOverlay = null;
  }

  function syncAddressClear() {
    if (!addressClear || !addressInput) return;
    addressClear.hidden = !addressInput.value;
  }

  function positionAddressSuggestions() {
    if (!addressMenu || !addressInput || addressMenu.hidden) return;
    positionFloatingMenu({
      anchor: addressInput.closest('.quote__field') || addressInput,
      menu: addressMenu,
      maxHeight: 272,
    });
  }

  addressOverlay = {
    invoker: addressInput,
    isOpen: () => Boolean(addressMenu && !addressMenu.hidden),
    open: () => {
      if (!addressMenu || !addressInput) return;
      addressMenu.hidden = false;
      addressInput.setAttribute('aria-expanded', 'true');
    },
    close: closeAddressSuggestions,
    position: positionAddressSuggestions,
    contains: (target) => Boolean(addressInput?.contains(target) || addressMenu?.contains(target)),
  };

  function chooseAddress(item) {
    if (!addressInput) return;
    addressInput.value = item.value;
    addressInput.dispatchEvent(new Event('change', { bubbles: true }));
    closeAddressSuggestions();
    addressInput.blur();
  }

  function setAddressActive(index) {
    if (!addressMenu || !addressInput || !addressItems.length) return;
    addressActiveIndex = (index + addressItems.length) % addressItems.length;
    addressMenu.querySelectorAll('.address-suggest__option').forEach((option, optionIndex) => {
      const active = optionIndex === addressActiveIndex;
      option.classList.toggle('is-active', active);
      option.setAttribute('aria-selected', String(active));
      if (active) {
        addressInput.setAttribute('aria-activedescendant', option.id);
        option.scrollIntoView({ block: 'nearest' });
      }
    });
  }

  function renderAddressSuggestions(items) {
    if (!addressMenu || !addressInput) return;
    addressItems = items;
    addressActiveIndex = -1;
    addressMenu.replaceChildren();
    const heading = document.createElement('span');
    heading.className = 'address-suggest__heading';
    heading.innerHTML = '<span>Адреса в Челябинске</span><span class="address-suggest__city">Только город</span>';
    addressMenu.appendChild(heading);
    items.forEach((item, index) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.id = `address-option-${index}`;
      option.className = 'address-suggest__option';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      const pin = document.createElement('span');
      pin.className = 'address-suggest__pin';
      pin.setAttribute('aria-hidden', 'true');
      pin.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 21s6.5-5.8 6.5-11a6.5 6.5 0 1 0-13 0c0 5.2 6.5 11 6.5 11Z"/><circle cx="12" cy="10" r="2.2"/></svg>';
      const text = document.createElement('span');
      text.className = 'address-suggest__text';
      const title = document.createElement('strong');
      title.textContent = item.title || item.value;
      const subtitle = document.createElement('small');
      subtitle.textContent = item.subtitle || 'Челябинск';
      text.append(title, subtitle);
      const arrow = document.createElement('span');
      arrow.className = 'address-suggest__arrow';
      arrow.setAttribute('aria-hidden', 'true');
      arrow.textContent = '→';
      option.append(pin, text, arrow);
      option.addEventListener('pointerdown', (event) => event.preventDefault());
      option.addEventListener('click', () => chooseAddress(item));
      addressMenu.appendChild(option);
    });
    if (items.length) openFloatingOverlay(addressOverlay);
    else closeAddressSuggestions();
  }

  addressInput?.addEventListener('input', () => {
    syncAddressClear();
    window.clearTimeout(addressTimer);
    addressController?.abort();
    const query = addressInput.value.trim();
    if (query.length < 2) {
      closeAddressSuggestions();
      return;
    }
    addressTimer = window.setTimeout(async () => {
      addressController = new AbortController();
      try {
        const response = await fetch(`/api/address-suggestions/?q=${encodeURIComponent(query)}`, {
          signal: addressController.signal,
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('Address suggestions unavailable');
        const result = await response.json();
        if (document.activeElement === addressInput && addressInput.value.trim() === query) {
          renderAddressSuggestions(result.suggestions || []);
        }
      } catch (error) {
        if (error.name !== 'AbortError') closeAddressSuggestions();
      }
    }, 280);
  });

  addressInput?.addEventListener('keydown', (event) => {
    if (addressMenu?.hidden) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setAddressActive(addressActiveIndex + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setAddressActive(addressActiveIndex - 1);
    } else if (event.key === 'Enter' && addressActiveIndex >= 0) {
      event.preventDefault();
      chooseAddress(addressItems[addressActiveIndex]);
    } else if (event.key === 'Escape') {
      closeAddressSuggestions();
    }
  });

  addressInput?.addEventListener('blur', () => {
    window.clearTimeout(addressTimer);
    addressController?.abort();
    window.setTimeout(closeAddressSuggestions, 120);
  });

  addressClear?.addEventListener('pointerdown', (event) => event.preventDefault());
  addressClear?.addEventListener('click', () => {
    if (!addressInput) return;
    addressInput.value = '';
    addressInput.dispatchEvent(new Event('input', { bubbles: true }));
    closeAddressSuggestions();
    addressInput.focus();
  });

  syncAddressClear();

  const visitInput = document.getElementById('visit-value');
  const visitToggle = document.getElementById('visit-toggle');
  const visitValue = visitToggle?.querySelector('.visit-picker__value');
  const visitMenu = document.getElementById('visit-picker-menu');
  const visitDays = document.getElementById('visit-days');
  const visitTimes = document.getElementById('visit-times');
  const visitMonthLabel = document.getElementById('visit-month-label');
  if (visitMenu && visitMenu.parentElement !== document.body) document.body.appendChild(visitMenu);
  const visitToday = new Date();
  visitToday.setHours(0, 0, 0, 0);
  const visitLastDay = new Date(visitToday);
  visitLastDay.setDate(visitLastDay.getDate() + 30);
  let visitSelectedDate = null;
  let visitSelectedTime = '';
  let visitVisibleMonth = new Date(visitToday.getFullYear(), visitToday.getMonth(), 1);
  const visitTimeSlots = ['Как можно скорее', '09:00–12:00', '12:00–15:00', '15:00–18:00', '18:00–21:00'];

  function sameDate(first, second) {
    return first && second
      && first.getFullYear() === second.getFullYear()
      && first.getMonth() === second.getMonth()
      && first.getDate() === second.getDate();
  }

  function visitDateLabel(date) {
    if (sameDate(date, visitToday)) return 'Сегодня';
    const tomorrow = new Date(visitToday);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (sameDate(date, tomorrow)) return 'Завтра';
    return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(date);
  }

  function syncVisitValue() {
    if (!visitInput || !visitValue) return;
    if (!visitSelectedDate || !visitSelectedTime) {
      visitInput.value = '';
      visitValue.textContent = 'Выберите дату и время';
      visitValue.classList.add('is-placeholder');
      return;
    }
    const value = `${visitDateLabel(visitSelectedDate)}, ${visitSelectedTime}`;
    visitInput.value = value;
    visitValue.textContent = value;
    visitValue.classList.remove('is-placeholder');
  }

  function renderVisitTimes() {
    if (!visitTimes) return;
    visitTimes.replaceChildren();
    visitTimeSlots.forEach((slot) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = slot;
      button.classList.toggle('is-selected', slot === visitSelectedTime);
      button.addEventListener('click', () => {
        if (!visitSelectedDate) visitSelectedDate = new Date(visitToday);
        visitSelectedTime = slot;
        syncVisitValue();
        renderVisitCalendar();
        closeVisitPicker();
      });
      visitTimes.appendChild(button);
    });
  }

  function renderVisitCalendar() {
    if (!visitDays || !visitMonthLabel) return;
    visitMonthLabel.textContent = new Intl.DateTimeFormat('ru-RU', {
      month: 'long',
      year: 'numeric',
    }).format(visitVisibleMonth);
    visitDays.replaceChildren();
    const firstWeekday = (visitVisibleMonth.getDay() + 6) % 7;
    const daysInMonth = new Date(
      visitVisibleMonth.getFullYear(),
      visitVisibleMonth.getMonth() + 1,
      0
    ).getDate();
    for (let index = 0; index < firstWeekday; index += 1) {
      const spacer = document.createElement('span');
      spacer.className = 'visit-picker__day-spacer';
      visitDays.appendChild(spacer);
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = new Date(visitVisibleMonth.getFullYear(), visitVisibleMonth.getMonth(), day);
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = String(day);
      button.className = 'visit-picker__day';
      button.disabled = date < visitToday || date > visitLastDay;
      button.classList.toggle('is-today', sameDate(date, visitToday));
      button.classList.toggle('is-selected', sameDate(date, visitSelectedDate));
      button.setAttribute('aria-label', new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric', month: 'long', weekday: 'long',
      }).format(date));
      button.addEventListener('click', () => {
        visitSelectedDate = date;
        renderVisitCalendar();
        renderVisitTimes();
      });
      visitDays.appendChild(button);
    }
    visitMenu?.querySelectorAll('[data-quick-day]').forEach((button) => {
      const quickDate = new Date(visitToday);
      quickDate.setDate(quickDate.getDate() + Number(button.dataset.quickDay));
      button.classList.toggle('is-selected', sameDate(quickDate, visitSelectedDate));
    });
  }

  function positionVisitPicker() {
    if (!visitMenu || !visitToggle || visitMenu.hidden) return;
    positionFloatingMenu({
      anchor: visitToggle.closest('.quote__field') || visitToggle,
      menu: visitMenu,
      maxHeight: 380,
      maxWidth: 300,
      preferredHeight: 350,
    });
  }

  function closeVisitPicker() {
    if (!visitMenu || !visitToggle) return;
    visitMenu.hidden = true;
    visitToggle.setAttribute('aria-expanded', 'false');
    visitToggle.closest('.quote__field')?.classList.remove('is-expanded');
    if (activeFloatingOverlay === visitOverlay) activeFloatingOverlay = null;
  }

  visitOverlay = {
    invoker: visitToggle,
    isOpen: () => Boolean(visitMenu && !visitMenu.hidden),
    open: () => {
      if (!visitMenu || !visitToggle) return;
      visitMenu.hidden = false;
      visitToggle.setAttribute('aria-expanded', 'true');
    },
    close: closeVisitPicker,
    position: positionVisitPicker,
    contains: (target) => Boolean(visitToggle?.contains(target) || visitMenu?.contains(target)),
  };

  function openVisitPicker() {
    if (!visitMenu || !visitToggle) return;
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    if (!visitSelectedDate) visitSelectedDate = new Date(visitToday);
    visitVisibleMonth = new Date(visitSelectedDate.getFullYear(), visitSelectedDate.getMonth(), 1);
    renderVisitCalendar();
    renderVisitTimes();
    openFloatingOverlay(visitOverlay);
  }

  visitToggle?.addEventListener('click', () => {
    if (visitMenu?.hidden) openVisitPicker();
    else closeVisitPicker();
  });

  visitMenu?.querySelectorAll('[data-quick-day]').forEach((button) => {
    button.addEventListener('click', () => {
      const date = new Date(visitToday);
      date.setDate(date.getDate() + Number(button.dataset.quickDay));
      visitSelectedDate = date;
      visitVisibleMonth = new Date(date.getFullYear(), date.getMonth(), 1);
      renderVisitCalendar();
      renderVisitTimes();
    });
  });

  visitMenu?.querySelectorAll('[data-month-step]').forEach((button) => {
    button.addEventListener('click', () => {
      visitVisibleMonth = new Date(
        visitVisibleMonth.getFullYear(),
        visitVisibleMonth.getMonth() + Number(button.dataset.monthStep),
        1
      );
      renderVisitCalendar();
    });
  });

  visitMenu?.querySelector('.visit-picker__reset')?.addEventListener('click', () => {
    visitSelectedDate = null;
    visitSelectedTime = '';
    syncVisitValue();
    renderVisitCalendar();
    renderVisitTimes();
  });

  document.addEventListener('pointerdown', (event) => {
    if (!activeFloatingOverlay || isFloatingOverlayTarget(activeFloatingOverlay, event.target)) return;
    closeFloatingOverlay(activeFloatingOverlay);
  });

  window.addEventListener('scroll', (event) => {
    if (!activeFloatingOverlay || isFloatingOverlayTarget(activeFloatingOverlay, event.target)) return;
    if (Date.now() - activeFloatingOverlay.openedAt < floatingOverlayGracePeriod) {
      window.requestAnimationFrame(() => activeFloatingOverlay?.position());
      return;
    }
    closeFloatingOverlay(activeFloatingOverlay);
  }, true);

  let mobileInputFocusedAt = 0;
  document.addEventListener('focusin', (event) => {
    if (event.target.matches?.('#address-input, .select__search')) mobileInputFocusedAt = Date.now();
  });
  window.addEventListener('scroll', (event) => {
    const active = document.activeElement;
    if (!active?.matches?.('#address-input, .select__search')) return;
    if (isFloatingOverlayTarget(activeFloatingOverlay, event.target)) return;
    if (Date.now() - mobileInputFocusedAt < 500) return;
    active.blur();
  }, true);
  const positionActiveFloatingOverlay = () => activeFloatingOverlay?.position();
  window.addEventListener('resize', positionActiveFloatingOverlay);
  window.visualViewport?.addEventListener('resize', positionActiveFloatingOverlay);
  renderVisitCalendar();
  renderVisitTimes();
  syncVisitValue();

  function collectQuoteDraft() {
    if (!quoteForm) return;
    const formData = new FormData(quoteForm);
    const issueValue = String(formData.get('issue') || '').trim();
    const selectedOption = quoteIssue?.selectedOptions?.[0];
    quoteDraft = {
      issue: selectedOption && issueValue ? selectedOption.text : issueValue,
      address: String(formData.get('address') || '').trim(),
      preferred_time: String(formData.get('preferred_time') || '').trim(),
      subcategory_ids: issueValue && /^\d+$/.test(issueValue) ? [Number(issueValue)] : [],
      work_ids: [],
    };
  }

  function openContactsFromQuote(invoker = document.activeElement) {
    collectQuoteDraft();
    contactsError.hidden = true;
    contactsForm.reset();
    openModal(modalContacts, invoker);
  }

  document.querySelectorAll('[data-open-contacts]').forEach((button) => {
    button.addEventListener('click', () => openContactsFromQuote(button));
  });

  quoteForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    collectQuoteDraft();
    if (!quoteDraft.issue && !quoteDraft.subcategory_ids.length) {
      openContactsFromQuote();
      contactsError.textContent = 'Укажите, что случилось, и оставьте телефон';
      contactsError.hidden = false;
      return;
    }
    openContactsFromQuote();
  });

  quoteForm?.addEventListener('reset', () => {
    window.requestAnimationFrame(() => {
      quoteForm.querySelectorAll('.select').forEach((widget) => {
        if (widget._sync) widget._sync();
        else syncSelectWidget(widget);
      });
      visitSelectedDate = null;
      visitSelectedTime = '';
      syncVisitValue();
      closeVisitPicker();
    });
  });

  let activeService = null;
  let modalWorkIds = new Set();
  let activeCategoryId = 'all';
  let selectedWorkIds = new Set();
  let toastTimer = 0;

  function normalize(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/ё/g, 'е')
      .trim();
  }

  function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU').format(price) + ' ₽';
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  const imageByCategory = {
    'Кухня': 'icon-service.svg',
    'Ванная': 'icon-install.svg',
    'Отопление': 'icon-heating.svg',
    'Водоснабжение': 'icon-pipes.svg',
    'Канализация': 'icon-clog.svg',
  };

  function allServices() {
    return categories.flatMap((category) => category.subcategories.map((sub) => ({
      ...sub,
      categoryId: category.id,
      categoryName: category.name,
      description: sub.description || category.description || `Монтаж, ремонт и обслуживание: ${sub.name.toLowerCase()}`,
      image: sub.image_url || `${servicesSection?.dataset.assetsBase || '/static/core/img/'}${imageByCategory[category.name] || 'icon-repair.svg'}`,
      hasCustomImage: Boolean(sub.image_url),
      works: sub.works || [],
    })));
  }

  const servicesCatalog = allServices();
  const searchableServices = servicesCatalog.map((service) => ({
    service,
    text: normalize(`${service.name} ${service.categoryName} ${service.description} ${service.works.map((work) => `${work.name} ${work.description || ''}`).join(' ')}`),
  }));
  const worksCatalog = servicesCatalog.flatMap((service) => service.works.map((work) => ({
    ...work,
    serviceId: Number(service.id),
    serviceName: service.name,
    categoryName: service.categoryName,
  })));

  function filteredServices() {
    const q = normalize(searchInput.value);
    const searchTerms = q.split(/\s+/).filter(Boolean);
    return searchableServices.filter(({ service, text }) => {
      const inCategory = activeCategoryId === 'all' || String(service.categoryId) === activeCategoryId;
      const matchesSearch = searchTerms.every((term) => text.includes(term));
      return q ? matchesSearch : inCategory;
    }).map(({ service }) => service);
  }

  function serviceMinPrice(service) {
    if (!service.works.length) return Number(service.price || 0);
    return Math.min(...service.works.map((work) => Number(work.price || 0)));
  }

  function allWorks() {
    return worksCatalog;
  }

  function selectedWorks() {
    return allWorks().filter((work) => selectedWorkIds.has(Number(work.id)));
  }

  function pluralWorks(count) {
    const lastTwo = count % 100;
    const last = count % 10;
    if (lastTwo >= 11 && lastTwo <= 14) return 'работ';
    if (last === 1) return 'работа';
    if (last >= 2 && last <= 4) return 'работы';
    return 'работ';
  }

  function updateSelectionUI() {
    const selected = selectedWorks();
    if (workList) workList.hidden = selected.length === 0;
    document.body.classList.toggle('has-work-list', selected.length > 0);
    if (selected.length) window.requestAnimationFrame(updateWorkListSpace);

    if (workListDetails && selected.length) {
      const total = selected.reduce((sum, service) => sum + Number(service.price || 0), 0);
      workListDetails.textContent = `${selected.length} ${pluralWorks(selected.length)} · ориентировочно от ${formatPrice(total)}`;
    }

    if (requestSummary) {
      requestSummary.hidden = selected.length === 0;
      requestSummary.innerHTML = selected.length
        ? `<strong>Вы выбрали:</strong><ul>${selected.map((work) => `<li>${work.serviceName}: ${work.name} — ${formatPrice(work.price)}</li>`).join('')}</ul>`
        : '';
    }
  }

  function updateWorkListSpace() {
    if (workList && !workList.hidden) {
      document.body.style.setProperty('--work-list-height', `${Math.ceil(workList.getBoundingClientRect().height)}px`);
    } else {
      document.body.style.removeProperty('--work-list-height');
    }
  }

  if (workList && 'ResizeObserver' in window) {
    new ResizeObserver(updateWorkListSpace).observe(workList);
  }

  function renderCategoryNav() {
    if (!categoryNav) return;
    categoryNav.replaceChildren();
    const track = document.createElement('div');
    track.className = 'category-nav__track';
    const rows = [document.createElement('div'), document.createElement('div')];
    rows.forEach((row) => {
      row.className = 'category-nav__row';
      track.appendChild(row);
    });

    [{ id: 'all', name: 'Все категории' }, ...categories].forEach((category, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'category-nav__item';
      button.textContent = category.name;
      button.dataset.categoryId = String(category.id);
      button.classList.toggle('is-active', String(category.id) === activeCategoryId);
      button.setAttribute('aria-pressed', String(String(category.id) === activeCategoryId));
      button.addEventListener('click', () => {
        activeCategoryId = String(category.id);
        categoryNav.querySelectorAll('.category-nav__item').forEach((item) => {
          const isActive = item.dataset.categoryId === activeCategoryId;
          item.classList.toggle('is-active', isActive);
          item.setAttribute('aria-pressed', String(isActive));
        });
        renderCatalog();
        button.scrollIntoView({
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
          block: 'nearest',
          inline: 'center',
        });
      });
      rows[index % 2].appendChild(button);
    });
    categoryNav.appendChild(track);
    requestAnimationFrame(updateCategoryScroll);
  }

  function updateCategoryScroll() {
    if (!categoryNav || !categoryScroll || !categoryScrollThumb) return;
    const maxScroll = categoryNav.scrollWidth - categoryNav.clientWidth;
    const visibleRatio = Math.min(1, categoryNav.clientWidth / categoryNav.scrollWidth);
    const thumbWidth = Math.max(18, visibleRatio * 100);
    const progress = maxScroll > 0 ? categoryNav.scrollLeft / maxScroll : 0;
    categoryScroll.hidden = maxScroll <= 1;
    categoryScrollThumb.style.width = `${thumbWidth}%`;
    const availableTrack = categoryScroll.clientWidth - categoryScrollThumb.offsetWidth;
    categoryScrollThumb.style.transform = `translateX(${progress * availableTrack}px)`;
    categoryScroll.setAttribute('aria-valuenow', String(Math.round(progress * 100)));
  }

  categoryNav?.addEventListener('scroll', updateCategoryScroll, { passive: true });

  function animateCategoryScrollTo(target) {
    if (!categoryNav) return;
    cancelAnimationFrame(categoryScrollAnimation);
    const start = categoryNav.scrollLeft;
    const maxScroll = categoryNav.scrollWidth - categoryNav.clientWidth;
    const destination = Math.max(0, Math.min(maxScroll, target));
    const distance = destination - start;
    if (Math.abs(distance) < 1) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      categoryNav.scrollLeft = destination;
      return;
    }
    const startedAt = performance.now();
    const duration = 360;
    const step = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      categoryNav.scrollLeft = start + distance * eased;
      if (progress < 1) categoryScrollAnimation = requestAnimationFrame(step);
    };
    categoryScrollAnimation = requestAnimationFrame(step);
  }

  categoryNav?.addEventListener('wheel', (event) => {
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    event.preventDefault();
    animateCategoryScrollTo(categoryNav.scrollLeft + event.deltaY * 1.8);
  }, { passive: false });

  function scrollCategoriesToPointer(event, smooth = false) {
    if (!categoryNav || !categoryScroll) return;
    const rect = categoryScroll.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const target = ratio * (categoryNav.scrollWidth - categoryNav.clientWidth);
    if (smooth) animateCategoryScrollTo(target);
    else {
      cancelAnimationFrame(categoryScrollAnimation);
      categoryNav.scrollLeft = target;
    }
  }

  categoryScroll?.addEventListener('pointerdown', (event) => {
    isCategoryScrollDragging = false;
    categoryPointerStartX = event.clientX;
    categoryScroll.setPointerCapture(event.pointerId);
    scrollCategoriesToPointer(event, true);
  });
  categoryScroll?.addEventListener('pointermove', (event) => {
    if (!categoryScroll.hasPointerCapture(event.pointerId)) return;
    if (Math.abs(event.clientX - categoryPointerStartX) > 4) {
      isCategoryScrollDragging = true;
      categoryScroll.classList.add('is-dragging');
    }
    if (isCategoryScrollDragging) scrollCategoriesToPointer(event);
  });
  categoryScroll?.addEventListener('pointerup', () => {
    isCategoryScrollDragging = false;
    categoryScroll.classList.remove('is-dragging');
  });
  categoryScroll?.addEventListener('pointercancel', () => {
    isCategoryScrollDragging = false;
    categoryScroll.classList.remove('is-dragging');
  });
  categoryScroll?.addEventListener('keydown', (event) => {
    if (!categoryNav || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const maxScroll = categoryNav.scrollWidth - categoryNav.clientWidth;
    const current = categoryNav.scrollLeft;
    const target = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? maxScroll
        : current + (event.key === 'ArrowRight' ? 180 : -180);
    animateCategoryScrollTo(target);
  });
  window.addEventListener('resize', updateCategoryScroll);

  function renderCatalog() {
    const list = filteredServices();
    track.replaceChildren();
    if (!list.length) {
      emptyState.hidden = false;
      if (catalogCount) catalogCount.textContent = '0 услуг';
      return;
    }
    emptyState.hidden = true;
    if (catalogCount) catalogCount.textContent = `${list.length} ${list.length === 1 ? 'услуга' : 'услуг'}`;
    list.forEach((service) => {
      const card = document.createElement('article');
      const selectedCount = service.works.filter((work) => selectedWorkIds.has(Number(work.id))).length;
      const isSelected = selectedCount > 0;
      card.className = `service-card${isSelected ? ' is-selected' : ''}`;
      card.innerHTML = `
        <div class="service-card__media${service.hasCustomImage ? ' has-photo' : ''}">
          <img src="${service.image}" alt="${service.name}" width="92" height="92">
          <span class="service-card__category">${service.categoryName}</span>
        </div>
        <div class="service-card__body">
          <h2 class="service-card__title">${service.name}</h2>
          <p class="service-card__description">${service.description}</p>
          <div class="service-card__footer">
            <p class="service-card__price"><span>${service.works.length} ${pluralWorks(service.works.length)} · от</span><strong>${formatPrice(serviceMinPrice(service))}</strong></p>
            <button class="service-card__action" type="button" aria-pressed="${isSelected}">
              ${isSelected ? `✓ Выбрано: ${selectedCount}` : 'Выбрать работы'}
            </button>
          </div>
        </div>
      `;
      card.querySelector('.service-card__action').addEventListener('click', (event) => {
        openServicesModal(service, event.currentTarget);
      });
      card.addEventListener('click', (event) => {
        if (event.target.closest('button')) return;
        openServicesModal(service, card.querySelector('.service-card__action'));
      });
      track.appendChild(card);
    });
  }

  function openModal(modal, invoker = document.activeElement) {
    if (!modal) return;
    if (activeFloatingOverlay) closeFloatingOverlay(activeFloatingOverlay);
    modal._returnFocus = invoker instanceof HTMLElement ? invoker : null;
    modal.hidden = false;
    document.body.classList.add('modal-open');
    for (const child of document.body.children) {
      if (child instanceof HTMLElement && child !== modal && !child.classList.contains('modal') && child !== toast) {
        child.inert = true;
      }
    }
    modal.querySelector('.modal__close')?.focus();
  }

  function closeModal(modal) {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    if (modalServices.hidden && modalContacts.hidden) {
      document.body.classList.remove('modal-open');
      for (const child of document.body.children) {
        if (child instanceof HTMLElement) child.inert = false;
      }
    }
    if (modal._returnFocus?.isConnected) modal._returnFocus.focus();
    modal._returnFocus = null;
  }

  function closeAllModals() {
    closeModal(modalServices);
    closeModal(modalContacts);
  }

  function openServicesModal(service, invoker) {
    activeService = service;
    modalWorkIds = new Set(
      service.works
        .map((work) => Number(work.id))
        .filter((id) => selectedWorkIds.has(id))
    );
    servicesError.hidden = true;
    servicesTitle.textContent = service.name;
    servicesSubtitle.textContent = 'Отметьте одну или несколько работ. Можно выбрать работы и в других услугах.';

    renderWorksChecklist();
    openModal(modalServices, invoker);
  }

  function renderWorksChecklist() {
    if (!activeService) return;
    const visibleWorks = activeService.works;

    checklist.replaceChildren();
    if (worksEmpty) worksEmpty.hidden = visibleWorks.length > 0;
    visibleWorks.forEach((work) => {
      const label = document.createElement('label');
      label.className = 'check-item';
      label.innerHTML = `
        <input type="checkbox" name="work" value="${work.id}" ${modalWorkIds.has(Number(work.id)) ? 'checked' : ''}>
        <span class="check-item__body">
          <span>
            <span class="check-item__name">${work.name}</span>
            ${work.description ? `<span class="check-item__description">${work.description}</span>` : ''}
          </span>
          <span class="check-item__price">${formatPrice(work.price)}</span>
        </span>
      `;
      const input = label.querySelector('input');
      input.addEventListener('change', () => {
        const id = Number(input.value);
        if (input.checked) modalWorkIds.add(id);
        else modalWorkIds.delete(id);
      });
      checklist.appendChild(label);
    });
  }

  function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
    }, 4200);
  }

  searchInput.addEventListener('input', () => {
    renderCatalog();
  });

  workListClear?.addEventListener('click', () => {
    selectedWorkIds.clear();
    renderCatalog();
    updateSelectionUI();
  });

  workListSubmit?.addEventListener('click', () => {
    const selected = selectedWorks();
    if (!selected.length) return;
    quoteDraft = {
      issue: selected.map((work) => `${work.serviceName}: ${work.name}`).join(', '),
      address: '',
      preferred_time: '',
      subcategory_ids: [...new Set(selected.map((work) => Number(work.serviceId)))],
      work_ids: selected.map((work) => Number(work.id)),
    };
    contactsError.hidden = true;
    contactsForm.reset();
    updateSelectionUI();
    openModal(modalContacts, workListSubmit);
  });

  servicesForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (activeService) {
      activeService.works.forEach((work) => selectedWorkIds.delete(Number(work.id)));
    }
    modalWorkIds.forEach((id) => selectedWorkIds.add(id));
    servicesError.hidden = true;
    closeModal(modalServices);
    renderCatalog();
    updateSelectionUI();
  });

  contactsForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    contactsError.hidden = true;

    const formData = new FormData(contactsForm);
    const currentlySelectedWorks = selectedWorks();
    const payload = {
      full_name: String(formData.get('full_name') || '').trim(),
      phone: String(formData.get('phone') || '').trim(),
      issue: quoteDraft.issue,
      address: quoteDraft.address,
      preferred_time: quoteDraft.preferred_time,
      subcategory_ids: quoteDraft.subcategory_ids.length
        ? quoteDraft.subcategory_ids
        : [...new Set(currentlySelectedWorks.map((work) => Number(work.serviceId)))],
      work_ids: quoteDraft.work_ids.length
        ? quoteDraft.work_ids
        : currentlySelectedWorks.map((work) => Number(work.id)),
    };

    const submitBtn = contactsForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    try {
      const response = await fetch('/api/requests/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.error || 'Не удалось отправить заявку');
      }

      window.location.assign(result.success_url || '/request-success/');
    } catch (error) {
      contactsError.textContent = error.message || 'Ошибка отправки';
      contactsError.hidden = false;
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.querySelectorAll('[data-modal-close]').forEach((el) => {
    el.addEventListener('click', () => {
      const modal = el.closest('.modal');
      if (modal) closeModal(modal);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Tab') {
      const modal = !modalContacts.hidden ? modalContacts : !modalServices.hidden ? modalServices : null;
      if (!modal) return;
      const focusable = [...modal.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]')]
        .filter((element) => element.getClientRects().length);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
      return;
    }
    if (event.key !== 'Escape') return;
    if (activeFloatingOverlay) {
      closeFloatingOverlay(activeFloatingOverlay, { restoreFocus: true });
      return;
    }
    if (!modalContacts.hidden) closeModal(modalContacts);
    else if (!modalServices.hidden) closeModal(modalServices);
  });

  renderCategoryNav();
  renderCatalog();
  updateSelectionUI();
})();
