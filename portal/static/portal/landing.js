// Playback starts only from an explicit user action. No media is fetched on load.
document.querySelectorAll('[data-video-player]').forEach((player) => {
  const video = player.querySelector('video');
  const summary = player.querySelector('summary');
  const error = player.querySelector('.video-error');
  summary.addEventListener('click', (event) => {
    event.preventDefault();
    player.open = !player.open;
    if (player.open) {
      video.play().catch(() => {
        // Native controls remain usable if a browser blocks scripted playback.
      });
    } else {
      video.pause();
    }
  });
  player.addEventListener('toggle', () => {
    if (!player.open) video.pause();
  });
  video.querySelector('source').addEventListener('error', () => { error.hidden = false; });
  video.addEventListener('error', () => { error.hidden = false; });
});

// Opening a link to a disclosure works with direct URLs and back/forward too.
function revealFragment() {
  if (!window.location.hash) return;
  const target = document.getElementById(window.location.hash.slice(1));
  if (!target) return;
  const parents = [];
  for (let node = target; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') parents.push(node);
  }
  parents.reverse().forEach((details) => { details.open = true; });
  if (parents.length) target.scrollIntoView();
}
window.addEventListener('hashchange', revealFragment);
revealFragment();
