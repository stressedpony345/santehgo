(() => {
  const state = { available: [], mine: [], latestId: 0, initialized: false };
  const availableList = document.getElementById('available-list');
  const mineList = document.getElementById('mine-list');
  const dialog = document.getElementById('request-dialog');
  const dialogContent = document.getElementById('dialog-content');
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
    return source.map((entry) => entry.name).join(' · ') || item.issue || 'Описание уточняется';
  }

  function card(item, mine = false) {
    const completionLabel = {
      pending: '<i class="request-card__status is-pending">На рассмотрении</i>',
      approved: '<i class="request-card__status is-approved">✓ Завершена</i>',
      rejected: '<i class="request-card__status is-rejected">Фото отклонено</i>',
    }[item.completion_status] || '';
    const article = document.createElement('article');
    article.className = `request-card${item.is_processed ? ' is-completed' : ''}`;
    article.innerHTML = `
      <div class="request-card__top">
        <div><p class="request-card__meta">${escapeHtml(item.created_at)}</p><p class="request-card__price">${money(item.price)} <small>заказ</small></p></div>
        <span class="request-card__id">${completionLabel} № ${item.id}</span>
      </div>
      <h2 class="request-card__title">${escapeHtml(item.issue || workNames(item))}</h2>
      <p class="request-card__works">${escapeHtml(workNames(item))}</p>
      <div class="request-card__actions">
        <button class="request-card__details" type="button" data-details="${item.id}">Подробнее</button>
        ${mine
          ? `<button class="request-card__complete${item.is_processed ? ' is-done' : ''}" type="button" data-complete="${item.id}" ${item.is_processed ? 'disabled' : ''}>${item.is_processed ? '<span>✓</span> Завершена' : 'Завершить заявку'}</button>`
          : `<button class="request-card__claim" type="button" data-claim="${item.id}">Взять заявку</button>`}
      </div>`;
    return article;
  }

  function render() {
    availableList.replaceChildren(...state.available.map((item) => card(item)));
    mineList.replaceChildren(...state.mine.map((item) => card(item, true)));
    mineList.querySelectorAll('[data-complete]').forEach((button) => {
      const item = findRequest(button.dataset.complete);
      if (!item) return;
      if (item.completion_status === 'pending') {
        button.disabled = true;
        button.textContent = 'На модерации';
      } else if (item.completion_status === 'approved') {
        button.disabled = true;
        button.textContent = '✓ Завершена';
      } else if (item.completion_status === 'rejected') {
        button.textContent = 'Сфотографировать заново';
      }
    });
    document.getElementById('available-count').textContent = state.available.length;
    document.getElementById('mine-count').textContent = state.mine.filter((item) => !item.is_processed).length;
    document.getElementById('nav-badge').textContent = state.available.length;
    document.getElementById('nav-badge').hidden = !state.available.length;
    document.getElementById('available-empty').hidden = Boolean(state.available.length);
    document.getElementById('mine-empty').hidden = Boolean(state.mine.length);
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
  }

  function findRequest(id) {
    return [...state.available, ...state.mine].find((item) => item.id === Number(id));
  }

  function openDetails(item) {
    const entries = item.works.length ? item.works : item.services;
    dialogContent.innerHTML = `
      <p class="view-kicker">Заявка № ${item.id}</p>
      <h2>${escapeHtml(item.issue || 'Заявка клиента')}</h2>
      <p class="detail-price">${money(item.price)}</p>
      <div class="detail-grid">
        <div class="detail-item"><small>Клиент</small><strong>${escapeHtml(item.full_name)}</strong></div>
        <div class="detail-item"><small>Когда удобно</small><strong>${escapeHtml(item.preferred_time || 'Уточнить')}</strong></div>
        <div class="detail-item"><small>Адрес</small><strong>${escapeHtml(item.address || 'Уточнить')}</strong></div>
        <div class="detail-item"><small>Создана</small><strong>${escapeHtml(item.created_at)}</strong></div>
      </div>
      <div class="detail-list"><h3>Состав работ</h3><ul>${entries.map((entry) => `<li><span>${escapeHtml(entry.name)}</span><strong>${money(entry.price)}</strong></li>`).join('') || '<li>Работы уточняются</li>'}</ul></div>
      <a class="detail-phone" href="tel:${escapeHtml(item.phone)}">Позвонить: ${escapeHtml(item.phone)}</a>`;
    dialog.showModal();
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

  async function submitCompletion(id, photo) {
    const form = new FormData();
    form.append('photo', photo);
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

  function captureCompletionPhoto(id) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment';
    input.addEventListener('change', async () => {
      const [photo] = input.files;
      if (!photo) return;
      try {
        await submitCompletion(id, photo);
        showToast('Фото отправлено на модерацию');
        await loadRequests();
      } catch (error) {
        showToast(error.message);
        await loadRequests();
      }
    }, { once: true });
    input.addEventListener('cancel', () => loadRequests(), { once: true });
    input.click();
  }

  document.addEventListener('click', (event) => {
    const complete = event.target.closest('[data-complete]');
    if (!complete || complete.disabled) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    complete.disabled = true;
    captureCompletionPhoto(complete.dataset.complete);
  }, true);

  document.addEventListener('click', async (event) => {
    const details = event.target.closest('[data-details]');
    if (details) return openDetails(findRequest(details.dataset.details));
    const claim = event.target.closest('[data-claim]');
    if (claim) {
      claim.disabled = true;
      try { await post(`/masters/api/requests/${claim.dataset.claim}/claim/`); showToast('Заявка добавлена в «Мои»'); await loadRequests(); }
      catch (error) { showToast(error.message); await loadRequests(); }
      return;
    }
    const complete = event.target.closest('[data-complete]');
    if (complete && !complete.disabled) {
      complete.disabled = true;
      try { await post(`/masters/api/requests/${complete.dataset.complete}/complete/`); showToast('Заявка завершена'); await loadRequests(); }
      catch (error) { showToast(error.message); complete.disabled = false; }
    }
  });

  document.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });

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
    });
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
