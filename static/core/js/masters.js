(() => {
  const state = { available: [], mine: [], mineFilter: 'active', latestId: 0, initialized: false };
  const availableList = document.getElementById('available-list');
  const mineList = document.getElementById('mine-list');
  const dialog = document.getElementById('request-dialog');
  const dialogContent = document.getElementById('dialog-content');
  const completionDialog = document.getElementById('completion-dialog');
  const completionForm = document.getElementById('completion-form');
  const toast = document.getElementById('app-toast');

  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  const money = (value) => new Intl.NumberFormat('ru-RU').format(value || 0) + ' ₽';
  const escapeHtml = (value) => String(value || '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => { toast.hidden = true; }, 3000);
  }

  function workNames(item) {
    const source = item.works.length ? item.works : item.services;
    return [...source, ...item.extra_works].map((entry) => entry.name).join(' · ') || item.issue || 'Описание уточняется';
  }

  function stage(item) {
    if (item.completion_status === 'approved') return item.payment_confirmed_at && (item.payment_method !== 'cash' || item.cash_status === 'confirmed') ? 'done' : 'payment';
    if (item.completion_status === 'pending') return 'review';
    return 'active';
  }

  function stageLabel(item) {
    if (item.completion_status === 'rejected') return 'Отчёт отклонён';
    if (item.completion_status === 'pending') return 'На проверке';
    if (item.completion_status === 'approved') {
      if (item.payment_confirmed_at) return item.payment_method === 'cash' && item.cash_status !== 'confirmed' ? 'Сдача наличных' : 'Оплачена · тест';
      return item.payment_method === 'unset' ? 'Выбор оплаты' : 'Ожидает оплаты';
    }
    return item.work_started_at ? 'В работе' : 'Передана мастеру';
  }

  function card(item, mine = false) {
    const completionLabel = mine ? `<i class="request-card__status is-${stage(item)}">${stageLabel(item)}</i>` : '';
    const nextAction = item.completion_status === 'approved' ? stage(item) === 'done' ? '' : 'Открыть оплату'
      : item.completion_status === 'pending' ? ''
      : !item.work_started_at && item.completion_status === 'none' ? 'Начать работу'
      : item.completion_status === 'rejected' ? 'Повторить отчёт' : 'Сдать отчёт';
    const article = document.createElement('article');
    article.className = `request-card${mine && stage(item) === 'done' ? ' is-completed' : ''}`;
    article.innerHTML = `
      <div class="request-card__top">
        <div><p class="request-card__meta">${escapeHtml(item.created_at)}</p><p class="request-card__price">${money(item.price)} <small>заказ</small></p></div>
        <span class="request-card__id">${completionLabel} № ${item.id}</span>
      </div>
      ${mine ? `<p class="request-card__payout">${item.completion_status === 'approved' ? 'Мастеру' : 'Мастеру после принятия'}: ${money(item.master_payout)}</p>` : ''}
      <h2 class="request-card__title">${escapeHtml(item.issue || workNames(item))}</h2>
      <p class="request-card__works">${escapeHtml(workNames(item))}</p>
      <div class="request-card__actions">
        <button class="request-card__details" type="button" data-details="${item.id}">Подробнее</button>
        ${mine
          ? (nextAction ? `<button class="request-card__complete" type="button" data-${!item.work_started_at && item.completion_status === 'none' ? 'start' : item.completion_status === 'approved' ? 'details' : 'complete'}="${item.id}">${nextAction}</button>` : '')
          : `<button class="request-card__claim" type="button" data-claim="${item.id}">Взять заявку</button>`}
      </div>`;
    return article;
  }

  function render() {
    availableList.replaceChildren(...state.available.map((item) => card(item)));
    const visible = state.mine.filter((item) => stage(item) === state.mineFilter);
    mineList.replaceChildren(...visible.map((item) => card(item, true)));
    document.querySelectorAll('[data-filter-count]').forEach((count) => {
      count.textContent = state.mine.filter((item) => stage(item) === count.dataset.filterCount).length;
    });
    document.getElementById('available-count').textContent = state.available.length;
    document.getElementById('mine-count').textContent = state.mine.length;
    document.getElementById('nav-badge').textContent = state.available.length;
    document.getElementById('nav-badge').hidden = !state.available.length;
    document.getElementById('available-empty').hidden = Boolean(state.available.length);
    document.getElementById('mine-empty').hidden = Boolean(visible.length);
  }

  async function loadRequests({ announce = false } = {}) {
    const response = await fetch('/masters/api/requests/', { headers: { Accept: 'application/json' } });
    if (response.status === 403 || response.redirected) return window.location.assign('/masters/login/');
    if (!response.ok) return;
    const data = await response.json();
    if (announce && state.initialized && data.latest_id > state.latestId && data.available.some((item) => item.id > state.latestId)) {
      showToast('Поступила новая заявка');
      if (Notification.permission === 'granted' && document.visibilityState === 'visible') {
        new Notification('Новая заявка', { body: 'Откройте общую очередь', icon: '/static/core/img/logo-mark.svg' });
      }
    }
    state.available = data.available;
    state.mine = data.mine;
    state.latestId = data.latest_id;
    state.initialized = true;
    document.getElementById('master-name').textContent = data.master.name;
    render();
    if (!document.querySelector('[data-view="income"]').hidden) loadEarnings();
  }

  function findRequest(id) {
    return [...state.available, ...state.mine].find((item) => item.id === Number(id));
  }

  function openDetails(item) {
    if (!item) return;
    const entries = item.works.length ? item.works : item.services;
    const canAdd = item.assigned_to && item.work_started_at && !item.is_processed && !['pending', 'approved'].includes(item.completion_status);
    dialogContent.innerHTML = `
      <p class="view-kicker">Заявка № ${item.id}</p>
      <h2>${escapeHtml(item.issue || 'Заявка клиента')}</h2>
      <p class="detail-stage">${item.assigned_to ? stageLabel(item) : 'В общей очереди'}</p>
      <p class="detail-price">${money(item.price)} <small>стоимость заказа</small></p>
      ${item.assigned_to ? `<p class="detail-payout">${item.completion_status === 'approved' ? 'Мастеру' : 'После принятия мастеру'}: ${money(item.master_payout)} · Компания: ${money(item.price - item.master_payout)}</p>` : ''}
      <div class="detail-grid">
        <div class="detail-item"><small>Клиент</small><strong>${escapeHtml(item.full_name)}</strong></div>
        <div class="detail-item"><small>Когда удобно</small><strong>${escapeHtml(item.preferred_time || 'Уточнить')}</strong></div>
        <div class="detail-item"><small>Адрес</small><strong>${escapeHtml(item.address || 'Уточнить')}</strong></div>
        <div class="detail-item"><small>Создана</small><strong>${escapeHtml(item.created_at)}</strong></div>
      </div>
      <div class="detail-list"><h3>Состав работ</h3><ul>${[...entries, ...item.extra_works].map((entry) => `<li><span>${escapeHtml(entry.name)}${item.extra_works.includes(entry) ? ' <small>Доп. работа</small>' : ''}</span><strong>${money(entry.price)}</strong></li>`).join('') || '<li>Работы уточняются</li>'}</ul></div>
      ${canAdd ? `<button class="extra-work-toggle" type="button" data-extra-toggle>+ Добавить доп. работу</button>
        <form class="extra-work-form" data-extra-form="${item.id}" hidden>
          <p>Найдите работу в каталоге или укажите свою. Стоимость добавится к заявке.</p>
          <label>Поиск по каталогу<input type="search" data-work-search placeholder="Например, замена смесителя" autocomplete="off"></label>
          <div class="extra-work-results" data-work-results role="listbox"></div>
          <label>Название работы<input name="name" maxlength="180" required placeholder="Что нужно сделать"></label>
          <label>Стоимость, ₽<input name="price" type="number" min="1" max="9999999999" step="1" required inputmode="numeric"></label>
          <button type="submit">Добавить к заявке</button>
        </form>` : ''}
      ${item.assigned_to && item.completion_status === 'none' && !item.work_started_at ? `<button class="detail-primary" type="button" data-start="${item.id}">Начать работу</button>` : ''}
      ${!item.assigned_to ? `<button class="detail-primary" type="button" data-claim="${item.id}">Взять заявку</button>` : ''}
      ${item.assigned_to && item.work_started_at && ['none', 'rejected'].includes(item.completion_status) ? `<button class="detail-primary" type="button" data-complete="${item.id}">${item.completion_status === 'rejected' ? 'Отправить исправленный отчёт' : 'Сдать отчёт'}</button>` : ''}
      ${item.completion_status === 'approved' ? `<div class="payment-panel"><h3>Оплата · тестовый режим</h3>${item.payment_method === 'unset' ? `<p>Уточните у клиента способ оплаты. Выбор способа не отмечает оплату.</p><div class="payment-actions"><button type="button" data-payment="${item.id}" data-method="qr">QR</button><button type="button" data-payment="${item.id}" data-method="cash">Наличные</button><button type="button" disabled title="Пока не подключён">Безнал</button></div>` : `<p>${item.payment_method === 'cash' ? 'Наличные' : 'QR'} · ${money(item.approved_total ?? item.price)}</p>${item.payment_method === 'qr' ? `<div class="demo-qr"><img src="/masters/api/requests/${item.id}/payment/qr/" alt="Тестовый QR для заявки № ${item.id}" loading="lazy"><small>Демонстрационный QR. Реальная оплата через него недоступна.</small></div>` : ''}${!item.payment_confirmed_at ? `<button type="button" data-confirm-payment="${item.id}">${item.payment_method === 'cash' ? 'Наличные получены' : 'Клиент оплатил · тест'}</button>` : `<p>Оплата отмечена ${escapeHtml(item.payment_confirmed_at)} · тест</p>`}${item.payment_method === 'cash' && item.payment_confirmed_at ? `<p>Доля компании к сдаче: ${money(item.cash_due)} до ${escapeHtml(item.cash_due_at)}. Доля мастера ${money(item.approved_payout)} остаётся у вас.</p><p>Сдача: ${item.cash_status === 'confirmed' ? 'подтверждена модератором' : item.cash_status === 'reported' ? 'ожидает подтверждения модератора' : 'ожидается'}</p>${item.cash_status === 'due' ? `<button type="button" data-report-cash="${item.id}">Сообщить о сдаче наличных</button>` : ''}` : ''}`}</div>` : ''}
      ${item.completion_status !== 'none' && item.completion_comment ? `<div class="detail-list"><h3>Комментарий модератору</h3><p>${escapeHtml(item.completion_comment)}</p></div>` : ''}
      ${item.completion_status !== 'none' && (item.completion_photo || item.completion_media.length) ? `<div class="detail-list"><h3>Материалы выполнения</h3><div class="detail-media">${item.completion_photo ? `<a href="${escapeHtml(item.completion_photo)}" target="_blank" rel="noopener">Фото 1</a>` : ''}${item.completion_media.map((media, index) => `<a href="${escapeHtml(media.url)}" target="_blank" rel="noopener">${media.kind === 'video' ? 'Видео' : 'Фото'} ${index + 2}</a>`).join('')}</div></div>` : ''}
      <a class="detail-phone" href="tel:${escapeHtml(item.phone)}">Позвонить: ${escapeHtml(item.phone)}</a>`;
    if (!dialog.open) dialog.showModal();
  }

  async function post(url, body = null) {
    const options = { method: 'POST', headers: { 'X-CSRFToken': decodeURIComponent(csrf()) } };
    if (body) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : { ok: false, error: 'Сервер временно не может выполнить запрос' };
    if (!response.ok) throw new Error(data.error || 'Не удалось выполнить действие');
    return data;
  }

  async function submitCompletion(id, form) {
    const response = await fetch(`/masters/api/requests/${id}/complete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': decodeURIComponent(csrf()) },
      body: form,
    });
    const data = (response.headers.get('content-type') || '').includes('application/json')
      ? await response.json()
      : { ok: false, error: 'Сервер временно не может принять фото' };
    if (!response.ok) throw new Error(data.error || 'Не удалось отправить фото');
    return data;
  }

  completionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = completionForm.querySelector('[type=submit]');
    const photos = completionForm.elements.photos.files;
    const videos = completionForm.elements.videos.files;
    if (photos.length < 1 || photos.length > 6 || videos.length > 2 || [...photos].some((file) => file.size > 10 * 1024 * 1024) || [...videos].some((file) => file.size > 50 * 1024 * 1024) || [...photos, ...videos].reduce((sum, file) => sum + file.size, 0) > 120 * 1024 * 1024) {
      showToast('Проверьте количество и размеры файлов'); return;
    }
    button.disabled = true;
    try {
      await submitCompletion(completionForm.dataset.requestId, new FormData(completionForm));
      completionDialog.close();
      showToast('Работа отправлена модератору');
      await loadRequests();
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; }
  });
  document.querySelector('[data-close-completion]').addEventListener('click', () => completionDialog.close());
  completionDialog.addEventListener('click', (event) => { if (event.target === completionDialog) completionDialog.close(); });

  document.addEventListener('click', async (event) => {
    const confirm = event.target.closest('[data-confirm-payment]');
    if (confirm) {
      confirm.disabled = true;
      try { await post(`/masters/api/requests/${confirm.dataset.confirmPayment}/payment/confirm/`); await loadRequests(); openDetails(findRequest(confirm.dataset.confirmPayment)); showToast('Оплата отмечена в тестовом режиме'); }
      catch (error) { showToast(error.message); confirm.disabled = false; }
      return;
    }
    const payment = event.target.closest('[data-payment]');
    if (payment) {
      payment.disabled = true;
      try { await post(`/masters/api/requests/${payment.dataset.payment}/payment/`, { method: payment.dataset.method }); await loadRequests(); openDetails(findRequest(payment.dataset.payment)); showToast('Тестовый способ оплаты сохранён'); }
      catch (error) { showToast(error.message); payment.disabled = false; }
      return;
    }
    const cash = event.target.closest('[data-report-cash]');
    if (cash) {
      cash.disabled = true;
      try { await post(`/masters/api/requests/${cash.dataset.reportCash}/cash-report/`); await loadRequests(); openDetails(findRequest(cash.dataset.reportCash)); showToast('Сообщение о сдаче отправлено модератору'); }
      catch (error) { showToast(error.message); cash.disabled = false; }
      return;
    }
    const toggle = event.target.closest('[data-extra-toggle]');
    if (toggle) {
      const form = dialogContent.querySelector('[data-extra-form]');
      form.hidden = !form.hidden;
      toggle.setAttribute('aria-expanded', String(!form.hidden));
      if (!form.hidden) form.querySelector('[data-work-search]').focus();
      return;
    }
    const choice = event.target.closest('[data-work-choice]');
    if (choice) {
      const form = choice.closest('form');
      form.dataset.workId = choice.dataset.workChoice;
      form.elements.name.value = choice.dataset.name;
      form.elements.price.value = choice.dataset.price;
      form.elements.name.readOnly = true;
      form.elements.price.readOnly = true;
      form.querySelector('[data-work-search]').value = choice.dataset.name;
      form.querySelector('[data-work-results]').replaceChildren();
      return;
    }
    const details = event.target.closest('[data-details]');
    if (details) return openDetails(findRequest(details.dataset.details));
    const claim = event.target.closest('[data-claim]');
    if (claim) {
      claim.disabled = true;
      try { await post(`/masters/api/requests/${claim.dataset.claim}/claim/`); showToast('Заявка добавлена в «Мои»'); await loadRequests(); }
      catch (error) { showToast(error.message); await loadRequests(); }
      return;
    }
    const start = event.target.closest('[data-start]');
    if (start) {
      start.disabled = true;
      try { await post(`/masters/api/requests/${start.dataset.start}/start/`); await loadRequests(); if (dialog.open) openDetails(findRequest(start.dataset.start)); showToast('Заявка в работе'); }
      catch (error) { showToast(error.message); start.disabled = false; }
      return;
    }
    const complete = event.target.closest('[data-complete]');
    if (complete && !complete.disabled) {
      if (dialog.open) dialog.close();
      completionForm.reset();
      completionForm.dataset.requestId = complete.dataset.complete;
      completionDialog.showModal();
      return;
    }
    if (event.target.closest('.request-card') && !event.target.closest('button, a')) {
      const card = event.target.closest('.request-card');
      openDetails(findRequest(card.querySelector('[data-details]').dataset.details));
    }
  });

  let searchSequence = 0;
  dialogContent.addEventListener('input', async (event) => {
    if (!event.target.matches('[data-work-search]')) return;
    const form = event.target.closest('form');
    delete form.dataset.workId;
    form.elements.name.readOnly = false;
    form.elements.price.readOnly = false;
    const results = form.querySelector('[data-work-results]');
    const query = event.target.value.trim();
    const sequence = ++searchSequence;
    results.replaceChildren();
    if (query.length < 2) return;
    try {
      const response = await fetch(`/masters/api/works/?q=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error();
      const { works } = await response.json();
      if (sequence !== searchSequence || !form.isConnected) return;
      results.innerHTML = works.map((work) => `<button type="button" role="option" data-work-choice="${work.id}" data-name="${escapeHtml(work.name)}" data-price="${work.price}"><span>${escapeHtml(work.name)}<small>${escapeHtml(work.service)}</small></span><strong>${money(work.price)}</strong></button>`).join('') || '<p>Ничего не найдено — можно указать работу вручную.</p>';
    } catch (_) { if (sequence === searchSequence) results.textContent = 'Поиск недоступен — укажите работу вручную.'; }
  });

  dialogContent.addEventListener('submit', async (event) => {
    if (!event.target.matches('[data-extra-form]')) return;
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('[type=submit]');
    button.disabled = true;
    try {
      const body = form.dataset.workId
        ? { work_id: Number(form.dataset.workId) }
        : { name: form.elements.name.value.trim(), price: form.elements.price.value };
      await post(`/masters/api/requests/${form.dataset.extraForm}/extra-works/`, body);
      await loadRequests();
      openDetails(findRequest(form.dataset.extraForm));
      showToast('Дополнительная работа добавлена, цена обновлена');
    } catch (error) { showToast(error.message); button.disabled = false; }
  });

  document.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });

  document.querySelectorAll('[data-mine-filter]').forEach((button) => button.addEventListener('click', () => {
    state.mineFilter = button.dataset.mineFilter;
    document.querySelectorAll('[data-mine-filter]').forEach((item) => {
      item.classList.toggle('is-active', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
    render();
  }));

  document.querySelectorAll('[data-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      const view = button.dataset.tab;
      document.querySelectorAll('[data-tab]').forEach((item) => item.classList.toggle('is-active', item === button));
      document.querySelectorAll('[data-view]').forEach((section) => {
        const active = section.dataset.view === view;
        section.hidden = !active;
        section.classList.toggle('is-active', active);
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (view === 'income') loadEarnings();
    });
  });

  async function loadEarnings() {
    try {
      const response = await fetch('/masters/api/earnings/');
      if (!response.ok) throw new Error('Не удалось загрузить доход');
      const data = await response.json();
      const metric = (label, value, note) => `<div class="income-metric"><small>${label}</small><strong>${value}</strong><span>${note}</span></div>`;
      document.getElementById('income-summary').innerHTML = [
        metric('Сегодня · мастеру', money(data.today.earned), `${data.today.count} принято · оборот ${money(data.today.turnover)}`),
        metric('Этот месяц · мастеру', money(data.month.earned), `${data.month.count} принято · оборот ${money(data.month.turnover)}`),
        metric('За всё время', money(data.all_time.earned), `${data.all_time.count} подтверждено модератором`),
        metric('К выводу · QR', money(data.available), data.is_monday ? 'Сегодня можно подать заявку' : 'Заявки принимаются по понедельникам'),
      ].join('');
      const max = Math.max(1, ...data.days.map((day) => day.amount));
      document.getElementById('income-chart').innerHTML = data.days.map((day) => `<div class="income-day" title="${day.date}: ${money(day.amount)}, заявок: ${day.count}"><strong>${money(day.amount)}</strong><div class="income-day__track"><span style="height:${Math.max(3, day.amount / max * 100)}%"></span></div><small>${day.date}</small></div>`).join('');
      document.getElementById('income-efficiency').innerHTML = [
        metric('Принято модератором', data.all_time.count, 'Все подтверждённые заявки'),
        metric('Доля принятых', `${data.approval_rate}%`, 'Среди рассмотренных заявок'),
        metric('Средний заработок', money(data.average_payout), 'На одну принятую заявку'),
        metric('В работе / на проверке', `${data.in_progress} / ${data.pending}`, 'Ещё не входит в заработок'),
      ].join('');
      document.getElementById('income-withdrawal').innerHTML = `<p>Доступно по подтверждённым QR-заявкам: <strong>${money(data.available)}</strong>. Наличные остаются у мастера в размере его доли; долю компании нужно сдать до конца дня. Незакрытая сдача: <strong>${money(data.cash_due)}</strong>${data.cash_count ? ` (${data.cash_count} требуют сдачи)` : ''}${data.cash_overdue ? ` · <strong class="income-overdue">Просрочено: ${data.cash_overdue}</strong>` : ''}.</p><p class="income-hint">Вывод доступен только каждый понедельник и требует подтверждения модератора. Сейчас режим имитации: никаких реальных переводов и QR-платежей нет.</p><button type="button" data-withdraw ${data.is_monday && data.available > 0 ? '' : 'disabled'}>Подать заявку на вывод ${money(data.available)}</button>`;
      document.getElementById('income-recent').innerHTML = data.recent.length ? `<div class="income-table-head"><span>Заявка / дата</span><span>Стоимость</span><span>Мастеру</span><span>Оплата</span></div>${data.recent.map((item) => `<div class="income-table-row"><span>№${item.id} · ${item.date}</span><span>${money(item.total)}</span><strong>${money(item.payout)}</strong><span>${{qr:'QR · тест',cash:'Наличные · тест',unset:'Не выбрана',bank:'Безнал'}[item.payment_method]}</span></div>`).join('')}` : '<p class="income-hint">Пока нет подтверждённых заявок.</p>';
      document.getElementById('income-history').innerHTML = data.withdrawals.length ? data.withdrawals.map((item) => `<div class="income-table-row"><span>№${item.id} · ${item.created_at}</span><strong>${money(item.amount)}</strong><span>${{pending:'Ожидает модератора',approved:'Подтверждено · тест',rejected:'Отклонено'}[item.status]}</span></div>`).join('') : '<p class="income-hint">Заявок на вывод пока нет.</p>';
    } catch (error) { document.getElementById('income-summary').textContent = error.message; }
  }

  document.getElementById('income-withdrawal').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-withdraw]');
    if (!button || button.disabled) return;
    button.disabled = true;
    try { await post('/masters/api/withdrawals/'); showToast('Заявка на вывод отправлена модератору (тест)'); await loadEarnings(); }
    catch (error) { showToast(error.message); button.disabled = false; }
  });

  function urlBase64ToUint8Array(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const raw = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from([...raw].map((char) => char.charCodeAt(0)));
  }

  async function enablePush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error('Уведомления не поддерживаются');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Разрешение на уведомления не выдано');
    const registration = await navigator.serviceWorker.ready;
    const keyResponse = await fetch('/masters/api/push/public-key/', { headers: { Accept: 'application/json' } });
    if (!keyResponse.ok || !(keyResponse.headers.get('content-type') || '').includes('application/json')) {
      throw new Error('Не удалось подключить уведомления. Попробуйте ещё раз.');
    }
    const { public_key: publicKey } = await keyResponse.json();
    if (!publicKey) throw new Error('Сервер не вернул ключ уведомлений');
    const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) });
    await post('/masters/api/push/subscribe/', subscription.toJSON());
    document.getElementById('notify-button').classList.add('is-on');
    showToast('Уведомления включены');
  }

  document.getElementById('notify-button').addEventListener('click', () => enablePush().catch((error) => showToast(error.message)));

  document.getElementById('password-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const message = document.getElementById('profile-message');
    const response = await fetch('/masters/profile/password/', { method: 'POST', headers: { 'X-CSRFToken': decodeURIComponent(csrf()) }, body: new FormData(form) });
    const data = await response.json();
    message.hidden = false;
    message.textContent = data.ok ? 'Пароль успешно изменён' : data.error;
    if (data.ok) form.reset();
  });

  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/masters/sw.js', { scope: '/masters/' });
  loadRequests();
  window.setInterval(() => loadRequests({ announce: true }), 20000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') loadRequests({ announce: true }); });
})();
