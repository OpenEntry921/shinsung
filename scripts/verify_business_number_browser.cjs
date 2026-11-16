// Local public-section checks. Uses the existing app; does not write application data.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.BUSINESS_NUMBER_BASE_URL || 'http://127.0.0.1:18081';
const artifacts = process.env.BUSINESS_NUMBER_ARTIFACTS || '/tmp/business-number-artifacts';
fs.mkdirSync(artifacts, { recursive: true });
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const width of [1440, 390, 360]) {
      const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1000 : 844 } });
      const page = await context.newPage();
      const errors = [], failures = [], mp4 = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error' && !m.text().includes('favicon.ico')) errors.push(m.text()); });
      page.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) failures.push([r.status(),r.url()]); });
      page.on('request', r => { if (r.url().includes('.mp4')) mp4.push(r.url()); });
      const response = await page.goto(base + '/');
      assert.equal(response.status(), 200);
      assert.equal(response.headers()['x-robots-tag'], 'noindex, nofollow');
      assert.match(response.headers()['content-security-policy'], /default-src 'self'/);
      assert.equal(await page.locator('.timeline-card').count(), 72);
      assert.equal(await page.locator('video[preload="none"][controls][playsinline]').count(), 3);
      assert.equal(await page.locator('#fundraising').count(), 1);
      assert.equal(await page.locator('a[href^="/prepare"]').count(), 0);
      assert.equal(await page.evaluate(() => document.querySelector('.hero-description').nextElementSibling.className), 'business-number-card');
      const button = page.getByRole('link', { name: '견적서의 번호, 직접 확인하기', exact: true });
      await page.screenshot({ path: path.join(artifacts, 'card-' + width + '.png'), fullPage: false });
      await button.focus();
      await page.keyboard.press('Enter');
      await page.waitForURL('**/#business-number-check');
      assert.ok(await page.locator('#business-number-title').evaluate(el => {
        const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom < innerHeight;
      }));
      const section = page.locator('#business-number-check');
      assert.equal(await section.locator('img').count(), 1);
      assert.ok(await section.locator('img').evaluate(img => img.complete && img.naturalWidth === 1350));
      assert.equal(await section.getByText('해당 홈택스 조회 화면: 미확보', { exact: true }).count(), 2);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const table = section.locator('.business-number-table').first();
      if (width < 600) {
        assert.ok(await table.evaluate(el => el.scrollWidth > el.clientWidth));
        await table.evaluate(el => { el.scrollLeft = el.scrollWidth; });
        assert.ok(await table.evaluate(el => el.scrollLeft > 0));
        await table.evaluate(el => { el.scrollLeft = 0; });
      }
      await page.screenshot({ path: path.join(artifacts, 'section-' + width + '.png'), fullPage: false });
      for (const linkName of ['비교 부분 확대 보기 (새 탭)', '견적서 전체 보기 (개인정보 가림, 새 탭)']) {
        const link = section.getByRole('link', { name: linkName, exact: true });
        const href = await link.getAttribute('href');
        assert.match(href, /\/static\/portal\/business-number\/estimate-2024-(detail|redacted)\.[a-f0-9]{12}\.jpg/);
        const popupPromise = context.waitForEvent('page');
        await link.click();
        const popup = await popupPromise;
        await popup.waitForLoadState('load');
        assert.ok(await popup.locator('img').evaluate(img => img.complete && img.naturalWidth > 0));
        await popup.close();
      }
      const official = section.getByRole('link', { name: '홈택스 공식 사이트에서 확인하기 (새 탭)', exact: true });
      assert.equal(await official.getAttribute('href'), 'https://www.hometax.go.kr');
      await page.goto(base + '/#business-number-check');
      assert.ok(await page.locator('#business-number-title').evaluate(el => el.getBoundingClientRect().top >= 0));
      const caseHref = await page.locator('.timeline-card').first().getAttribute('href');
      assert.equal((await context.request.get(base + caseHref)).status(), 200);
      const protectedResponse = await context.request.get(base + '/prepare/events/T01/', { maxRedirects: 0 });
      assert.equal(protectedResponse.status(), 302);
      assert.equal(protectedResponse.headers().location, '/prepare/');
      assert.deepEqual(errors, []);
      assert.deepEqual(failures, []);
      assert.deepEqual(mp4, []);
      results.push({ width, status:'pass', overflow:false, errors, failures, initialMP4Requests:mp4.length, imageZoom:'pass', keyboardAnchor:'pass' });
      await context.close();
    }
    fs.writeFileSync(path.join(artifacts, 'browser-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
