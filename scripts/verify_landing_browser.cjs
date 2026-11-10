// Optional browser regression check. Requires Playwright and Chromium; see docs/LANDING.md.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.LANDING_BASE_URL || 'http://127.0.0.1:8001';
const artifacts = process.env.LANDING_ARTIFACTS || '/tmp/laity-landing-artifacts';
const ready = process.env.LANDING_MEDIA !== 'absent';
fs.mkdirSync(artifacts, { recursive: true });
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1000 : 844 },
        extraHTTPHeaders: process.env.LANDING_FORWARDED_HTTPS === 'true' ? { 'X-Forwarded-Proto': 'https' } : {} });
      const page = await context.newPage();
      const errors = [], mediaRequests = [], failures = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      page.on('request', r => { if (r.resourceType() === 'media') mediaRequests.push(r.url()); });
      page.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) failures.push([r.status(), r.url()]); });
      await page.goto(base + '/');
      await page.evaluate(() => document.fonts.ready);
      assert.equal(await page.locator('.timeline-card').count(), 72);
      assert.equal(await page.locator('.pending-label').count(), ready ? 0 : 3);
      assert.equal(await page.locator('video').count(), ready ? 3 : 0);
      assert.equal(await page.locator('a[href^="/prepare"],a[href^="/login"],a[href^="/apply"],input').count(), 0);
      assert.equal(await page.locator('[data-recent-record]').count(), 3);
      assert.equal(await page.locator('#progress-details').getAttribute('open'), null);
      assert.equal(await page.locator('#roadmap-details').getAttribute('open'), null);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.equal(mediaRequests.length, 0, 'preload=none must avoid initial video downloads');
      await page.screenshot({ path: path.join(artifacts, `${width}-${ready ? 'ready' : 'pending'}-first.png`) });
      await page.screenshot({ path: path.join(artifacts, `${width}-${ready ? 'ready' : 'pending'}-full.png`), fullPage: true });
      const initialMediaRequests = mediaRequests.length;
      await page.getByRole('link', { name: '핵심 내용 보기' }).click();
      assert.equal(new URL(page.url()).hash, '#videos');
      await page.getByRole('link', { name: '사건 기록 살펴보기' }).click();
      assert.equal(new URL(page.url()).hash, '#timeline');
      await page.goBack();
      assert.equal(new URL(page.url()).hash, '#videos');
      for (const hash of ['dashboard', 'roadmap', 'timeline', 'progress-details', 'roadmap-details']) {
        await page.goto(base + '/#' + hash);
        assert.equal(await page.locator('#' + hash).isVisible(), true);
        if (hash.endsWith('details')) assert.equal(await page.locator('#' + hash).getAttribute('open'), '');
      }
      await page.goto(base + '/');
      const related = page.locator('.video-card .related-records summary').first();
      await related.focus(); await page.keyboard.press('Enter');
      const detailLink = page.locator('.video-card .related-records a').first();
      assert.equal(await detailLink.isVisible(), true);
      await detailLink.click();
      assert.match(page.url(), /\/cases\/material\/T24\/$/);
      await page.goBack();
      if (ready) {
        for (let i = 0; i < 3; i++) {
          const player = page.locator('[data-video-player]').nth(i);
          const summary = player.locator('summary');
          await summary.focus(); await page.keyboard.press('Enter');
          const video = player.locator('video');
          await video.evaluate(v => new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('playback did not start in 10 seconds')), 10000);
            const done = () => { clearTimeout(timeout); resolve(); };
            if (v.currentTime > 0 && !v.paused) return done();
            v.addEventListener('timeupdate', done, { once: true });
            v.addEventListener('error', () => reject(new Error('playback error')), { once: true });
          }));
          await video.evaluate(v => v.pause());
          assert.equal(await video.evaluate(v => v.paused), true);
          await video.evaluate(v => new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('seek did not finish in 10 seconds')), 10000);
            v.addEventListener('seeked', () => { clearTimeout(timeout); resolve(); }, { once: true }); v.currentTime = 2;
          }));
          assert.equal(await video.evaluate(v => Math.abs(v.currentTime - 2) < .2), true);
          await video.evaluate(v => v.requestFullscreen());
          assert.equal(await page.evaluate(() => document.fullscreenElement?.tagName), 'VIDEO');
          await page.evaluate(() => document.exitFullscreen());
          assert.equal(await video.evaluate(v => v.controls && v.playsInline && v.preload === 'none' && !v.autoplay && getComputedStyle(v).objectFit === 'contain'), true);
          await summary.click();
          assert.equal(await video.evaluate(v => v.paused), true);
        }
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(failures, []);
      assert.deepEqual(errors, []);
      results.push({ width, media: ready ? 'installed media' : 'absent', timeline: 72, initialMediaRequests, anchorsAndBack: 'pass', keyboard: 'pass', playback: ready ? 'play/pause/seek/fullscreen pass' : 'not applicable', consoleErrors: errors, overflow: false });
      await context.close();
    }
    fs.writeFileSync(path.join(artifacts, ready ? 'ready-results.json' : 'pending-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
