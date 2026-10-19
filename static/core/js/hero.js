(() => {
  const hero = document.getElementById('hero');
  const scrollCue = document.getElementById('hero-scroll');

  if (!scrollCue || !hero) return;

  const syncScrollCue = () => {
    const passed = window.scrollY > hero.offsetHeight * 0.18;
    scrollCue.classList.toggle('is-hidden', passed);
  };

  window.addEventListener('scroll', syncScrollCue, { passive: true });
  syncScrollCue();

  scrollCue.addEventListener('click', (event) => {
    const target = document.getElementById('content');
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
})();
