// Optional Playwright checks for the published fundraising section.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.FUNDRAISING_BASE_URL || 'http://127.0.0.1:8000';
const artifacts = process.env.FUNDRAISING_ARTIFACTS || '/tmp/fundraising-artifacts';
fs.mkdirSync(artifacts, { recursive: true });

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1000 : 844 } });
      await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base });
      const page = await context.newPage();
      const errors = [], failures = [], mediaRequests = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      page.on('response', r => { if (r.status() >= 400) failures.push([r.status(), r.url()]); });
      page.on('request', r => { if (r.resourceType() === 'media') mediaRequests.push(r.url()); });
      const response = await page.goto(base + '/');
      assert.equal(response.headers()['x-robots-tag'], 'noindex, nofollow');
      const action = page.locator('.hero-actions').getByRole('link', { name: '모금 안내', exact: true });
      await action.scrollIntoViewIfNeeded();
      const box = await action.boundingBox();
      assert.ok(box.y >= 0 && box.y + box.height <= page.viewportSize().height, 'fundraising action must be visible after scrolling');
      assert.equal(await page.locator('.fundraising-status').count(), 1);
      assert.match(await page.locator('.fundraising-status').innerText(), /카카오뱅크 모임통장 · 계좌 공개 중/);
      assert.equal(await page.locator('#fundraising-account-number').innerText(), '3333-09-0895440');
      assert.equal(await page.getByText('교회를 사랑하는 모임', { exact: true }).count(), 1);
      assert.equal(await page.locator('form,input,a[href^="/prepare"],a[href^="/login"]').count(), 0);
      assert.equal(await page.locator('.timeline-card').count(), 72);
      assert.equal(await page.locator('video').count(), 3);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({ path: path.join(artifacts, `${width}-first.png`) });
      await action.focus(); await page.keyboard.press('Enter');
      assert.equal(new URL(page.url()).hash, '#fundraising');
      assert.equal(await page.locator('#fundraising').evaluate(e => e.contains(document.activeElement)), true);
      const heading = await page.locator('#fundraising-title').boundingBox();
      assert.ok(heading.y >= 0 && heading.y < page.viewportSize().height);
      assert.equal(await page.locator('.fundraising-body').evaluate(e => !!e.closest('details')), false);
      for (const [name, id] of [
        ['모금 목적', 'fundraising-purpose'],
        ['관리·보고 방식', 'fundraising-management'],
        ['후원 계좌', 'fundraising-account-title'],
      ]) {
        await page.locator('.fundraising-links').getByRole('link', { name, exact: true }).click();
        assert.equal(new URL(page.url()).hash, '#' + id);
        assert.equal(await page.locator('#' + id).isVisible(), true);
      }
      await page.locator('#fundraising').screenshot({ path: path.join(artifacts, `${width}-detail.png`) });
      await page.goto(base + '/#fundraising');
      assert.equal(await page.locator('#fundraising').isVisible(), true);
      const account = page.locator('#fundraising-account-number');
      assert.equal(await account.evaluate(e => {
        const range = document.createRange();
        range.selectNodeContents(e);
        const bounds = range.getBoundingClientRect();
        return bounds.left >= 0 && bounds.right <= innerWidth && Number(getComputedStyle(e).fontWeight) >= 700;
      }), true);
      await page.getByRole('button', { name: '계좌번호 복사' }).click();
      await page.waitForFunction(() => document.querySelector('.fundraising-copy-result').textContent === '계좌번호가 복사되었습니다');
      assert.equal(await page.evaluate(() => navigator.clipboard.readText()), '3333090895440');
      for (const hash of ['videos', 'issues', 'dashboard', 'roadmap']) {
        await page.goto(base + '/#' + hash);
        assert.equal(await page.locator('#' + hash).isVisible(), true);
      }
      await page.goto(base + '/');
      await page.locator('.hero-actions').getByRole('link', { name: '시간순 사건 기록' }).click();
      assert.equal(new URL(page.url()).hash, '#timeline');
      await page.locator('.timeline-card').first().click();
      assert.match(page.url(), /\/cases\/material\/T01\/$/);
      await page.goBack();
      assert.equal(new URL(page.url()).hash, '#timeline');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(errors, []); assert.deepEqual(failures, []);
      assert.equal(mediaRequests.length, 0);
      results.push({ width, meetingShortcut: 'pass', keyboardAndFragment: 'pass', accountAndClipboard: 'pass', existingLinks: 'pass', overflow: false, consoleErrors: [], initialMediaRequests: 0 });
      await context.close();
    }
    for (const mode of ['denied', 'unavailable']) {
      const context = await browser.newContext();
      await context.addInitScript((mode) => {
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: mode === 'unavailable' ? undefined : { writeText: async () => { throw new DOMException('Test permission denial', 'NotAllowedError'); } } });
      }, mode);
      const page = await context.newPage();
      await page.goto(base + '/#fundraising');
      await page.getByRole('button', { name: '계좌번호 복사' }).click();
      await page.waitForFunction(() => !document.querySelector('[data-copy-fundraising-account]').disabled);
      const result = await page.locator('.fundraising-copy-result').innerText();
      assert.match(result, /복사하지 못했습니다/);
      results.push({ clipboardMode: mode, copyResult: 'pass' });
      await context.close();
    }
    fs.writeFileSync(path.join(artifacts, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
