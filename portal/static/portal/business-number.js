(() => {
  const dialog = document.getElementById('business-number-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  let trigger;
  const holder = dialog.querySelector('.business-number-dialog-image');
  const zoom = dialog.querySelector('[data-business-evidence-zoom]');
  const resetZoom = () => {
    holder.classList.remove('expanded');
    zoom.setAttribute('aria-pressed', 'false');
    zoom.textContent = '원본 크기로 보기';
  };
  zoom.addEventListener('click', () => {
    const expanded = holder.classList.toggle('expanded');
    zoom.setAttribute('aria-pressed', String(expanded));
    zoom.textContent = expanded ? '화면에 맞추기' : '원본 크기로 보기';
  });
  document.querySelectorAll('[data-business-evidence]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      trigger = link;
      resetZoom();
      const image = new Image();
      image.src = link.href;
      image.alt = link.dataset.evidenceCaption;
      holder.replaceChildren(image);
      dialog.querySelector('.business-number-dialog-caption').textContent = image.alt;
      dialog.showModal();
    });
  });
  dialog.querySelector('[data-business-evidence-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    holder.replaceChildren();
    if (trigger) trigger.focus({ preventScroll: true });
  });
})();
