// Run against local Gunicorn/WhiteNoise. No application data is written.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.BUSINESS_NUMBER_BASE_URL || 'http://127.0.0.1:18082';
const artifacts = process.env.BUSINESS_NUMBER_ARTIFACTS || '/tmp/business-number-evidence';
const expectedImages = Number(process.env.BUSINESS_NUMBER_IMAGES || 1);
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
      await page.screenshot({ path: path.join(artifacts, 'card-' + width + '.png') });
      const button = page.getByRole('link', { name: '견적서와 조회 결과 확인하기', exact: true });
      await button.focus(); await page.keyboard.press('Enter');
      await page.waitForURL('**/#business-number-check');
      assert.ok(await page.locator('#business-number-title').evaluate(el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom < innerHeight; }));
      const section = page.locator('#business-number-check');
      assert.equal(await section.locator('img').count(), expectedImages);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(artifacts, 'section-' + width + '.png') });
      const rows = page.locator('.business-number-comparison tbody tr');
      assert.equal(await rows.count(), 3);
      const expected = [['2021. 9. 25.','581-16-00460','51,890,000원'],['2023. 10. 10.','581-16-00460','12,090,000원'],['2024. 2. 25.','128-03-18446','15,444,000원']];
      for (let i = 0; i < 3; i++) {
        for (const text of expected[i]) assert.ok((await rows.nth(i).innerText()).includes(text));
        assert.equal(await rows.nth(i).evaluate(el => getComputedStyle(el).display), width < 700 ? 'block' : 'table-row');
      }
      await page.locator('.business-number-comparison').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(artifacts, 'comparison-' + width + '.png') });
      const links = section.locator('[data-business-evidence]');
      for (let i = 0; i < await links.count(); i++) {
        const link = links.nth(i);
        const href = await link.getAttribute('href');
        assert.match(href, /\/static\/portal\/business-number\/[^/]+\.[a-f0-9]{12}\.(jpg|png)/);
        const imageResponse = await context.request.get(base + href);
        assert.equal(imageResponse.status(), 200);
        assert.match(imageResponse.headers()['content-type'], /^image\//);
        await link.focus(); await page.keyboard.press('Enter');
        const dialog = page.locator('#business-number-dialog');
        await dialog.waitFor({ state: 'visible' });
        await page.waitForFunction(() => { const im = document.querySelector('.business-number-dialog-image img'); return im && im.complete && im.naturalWidth > 0; });
        await dialog.getByRole('button', { name: '원본 크기로 보기' }).click();
        assert.equal(await dialog.getByRole('button', { name: '화면에 맞추기' }).getAttribute('aria-pressed'), 'true');
        await page.screenshot({ path: path.join(artifacts, 'zoom-' + width + '-' + i + '.png') });
        if (i % 2 === 0) await page.keyboard.press('Escape');
        else await dialog.getByRole('button', { name: '닫기', exact: true }).click();
        assert.equal(await dialog.isVisible(), false);
        assert.equal(await link.evaluate(el => el === document.activeElement), true);
      }
      await page.goto(base + '/#business-number-check');
      assert.ok(await page.locator('#business-number-title').evaluate(el => el.getBoundingClientRect().top >= 0));
      const caseHref = await page.locator('.timeline-card').first().getAttribute('href');
      assert.equal((await context.request.get(base + caseHref)).status(), 200);
      const protectedResponse = await context.request.get(base + '/prepare/events/T01/', { maxRedirects: 0 });
      assert.equal(protectedResponse.status(), 302);
      assert.equal(protectedResponse.headers().location, '/prepare/');
      assert.deepEqual(errors, []); assert.deepEqual(failures, []); assert.deepEqual(mp4, []);
      results.push({ width, status:'pass', imageCount:expectedImages, mobileCards:width < 700, dialogKeyboardCloseAndFocus:'pass', overflow:false, errors, failures, initialMP4Requests:0 });
      await context.close();
    }
    const nojs = await browser.newContext({ javaScriptEnabled:false, viewport:{width:390,height:844} });
    const page = await nojs.newPage();
    await page.goto(base + '/');
    await page.getByRole('link', { name: '견적서와 조회 결과 확인하기', exact: true }).click();
    assert.equal(new URL(page.url()).hash, '#business-number-check');
    const href = await page.locator('[data-business-evidence]').first().getAttribute('href');
    await page.locator('[data-business-evidence]').first().click();
    assert.equal(new URL(page.url()).pathname, href);
    assert.ok(await page.locator('img').evaluate(el => el.complete && el.naturalWidth > 0));
    results.push({ javaScriptDisabled:'anchor and real image fallback pass' });
    await nojs.close();
    fs.writeFileSync(path.join(artifacts, 'browser-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
