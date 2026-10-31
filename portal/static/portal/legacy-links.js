// Fragment identifiers are never sent to the server; resolve old bookmarks here.
if (window.location.pathname === '/') {
  const hash = window.location.hash;
  if (/^#material-E(?:0[1-9]|[12][0-9]|30)$/.test(hash)) {
    window.location.replace('/cases/material/' + hash.slice(10) + '/');
  } else if (/^#comment-[0-9]+$/.test(hash)) {
    window.location.replace('/comment-link/' + hash.slice(9) + '/');
  }
}
