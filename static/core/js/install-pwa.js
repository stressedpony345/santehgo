(() => {
  const banner = document.getElementById('pwa-install');
  const installButton = document.getElementById('pwa-install-button');
  const dismissButton = document.getElementById('pwa-install-dismiss');
  const help = document.getElementById('install-help');
  const helpTitle = document.getElementById('install-help-title');
  const helpSteps = document.getElementById('install-help-steps');
  if (!banner || !installButton || !help) return;

  let installPrompt = null;
  const standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const android = /android/i.test(navigator.userAgent);

  const showBanner = () => {
    if (!standalone && sessionStorage.getItem('pwa-install-hidden') !== '1') banner.hidden = false;
  };

  const showHelp = () => {
    const steps = ios
      ? [
          ['1', 'Откройте меню «Поделиться»', 'Нажмите значок квадрата со стрелкой вверх в Safari.'],
          ['2', 'Выберите «На экран Домой»', 'Если пункта не видно — прокрутите список действий вниз.'],
          ['3', 'Нажмите «Добавить»', 'Приложение появится на домашнем экране iPhone.'],
        ]
      : [
          ['1', 'Откройте меню браузера', 'Нажмите ⋮ в Яндекс Браузере или Chrome.'],
          ['2', 'Выберите установку', 'Нажмите «Установить приложение» или «Добавить на главный экран».'],
          ['3', 'Подтвердите', 'Иконка САНТЕХГО появится среди приложений телефона.'],
        ];
    helpTitle.textContent = ios ? 'Установка на iPhone' : 'Установка на телефон';
    helpSteps.innerHTML = steps.map(([number, title, text]) => `<div><b>${number}</b><span><strong>${title}</strong><small>${text}</small></span></div>`).join('');
    help.showModal();
  };

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    showBanner();
  });

  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    banner.hidden = true;
  });

  installButton.addEventListener('click', async () => {
    if (!installPrompt) return showHelp();
    const result = await installPrompt.prompt();
    installPrompt = null;
    if (result.outcome === 'accepted') banner.hidden = true;
    else showHelp();
  });

  dismissButton?.addEventListener('click', () => {
    banner.hidden = true;
    sessionStorage.setItem('pwa-install-hidden', '1');
  });
  help.querySelector('.install-help__close')?.addEventListener('click', () => help.close());
  help.querySelector('.install-help__done')?.addEventListener('click', () => help.close());
  help.addEventListener('click', (event) => { if (event.target === help) help.close(); });

  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/masters/sw.js', { scope: '/masters/' });
  window.setTimeout(showBanner, 800);
})();
