document.querySelectorAll('.comparison').forEach((comparison) => {
  const range = comparison.querySelector('.comparison__range');

  const updatePosition = () => {
    comparison.style.setProperty('--comparison-position', `${range.value}%`);
  };

  range.addEventListener('input', updatePosition);
  updatePosition();
});
