// Optional Playwright checks. Test publication data stays in a child process;
// no account settings, repository files or application database are changed.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const base = process.env.FUNDRAISING_BASE_URL || 'http://127.0.0.1:8000';
const artifacts = process.env.FUNDRAISING_ARTIFACTS || '/tmp/fundraising-artifacts';
fs.mkdirSync(artifacts, { recursive: true });
const publicationFixture = execFileSync(path.join(root, '.venv/bin/python'), ['-c', `
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from unittest.mock import patch
from django.test import Client,override_settings
from portal.fundraising import FUNDRAISING
with override_settings(SECURE_SSL_REDIRECT=False), patch.dict(FUNDRAISING, dict(status='published', account_number='TEST-ACCOUNT-NOT-REAL',account_holder='TEST-HOLDER-NOT-REAL')):
    print(Client().get('/').content.decode())
`], { cwd: root, env: { ...process.env, APP_MODE: 'development' }, encoding: 'utf8' });

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1000 : 844 } });
      const page = await context.newPage();
      const errors = [], failures = [], mediaRequests = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      page.on('response', r => { if (r.status() >= 400) failures.push([r.status(), r.url()]); });
      page.on('request', r => { if (r.resourceType() === 'media') mediaRequests.push(r.url()); });
      const response = await page.goto(base + '/');
      assert.equal(response.headers()['x-robots-tag'], 'noindex, nofollow');
      const card = page.locator('.fundraising-card');
      const action = card.getByRole('link', { name: '모금 취지와 참여 안내' });
      const box = await action.boundingBox();
      assert.ok(box.y >= 0 && box.y + box.height <= page.viewportSize().height, 'fundraising action must be in the first viewport');
      assert.equal(await page.locator('.fundraising-status').count(), 2);
      for (const status of await page.locator('.fundraising-status').all()) assert.match(await status.innerText(), /카카오뱅크 모임통장 · 계좌 준비 중/);
      assert.equal(await page.locator('[data-copy-fundraising-account],#fundraising-account-number,.fundraising-account dt').count(), 0);
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
      await page.locator('#fundraising').screenshot({ path: path.join(artifacts, `${width}-detail.png`) });
      await page.goto(base + '/#fundraising');
      assert.equal(await page.locator('#fundraising').isVisible(), true);
      for (const hash of ['videos', 'issues', 'dashboard', 'roadmap', 'timeline']) {
        await page.goto(base + '/#' + hash);
        assert.equal(await page.locator('#' + hash).isVisible(), true);
      }
      await page.locator('.timeline-card').first().click();
      assert.match(page.url(), /\/cases\/material\/T01\/$/);
      await page.goBack();
      assert.equal(new URL(page.url()).hash, '#timeline');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.deepEqual(errors, []); assert.deepEqual(failures, []);
      assert.equal(mediaRequests.length, 0);
      results.push({ width, firstViewportAction: 'pass', keyboardAndFragment: 'pass', state: 'preparing, no account fields or copy button', existingLinks: 'pass', overflow: false, consoleErrors: [], initialMediaRequests: 0 });
      await context.close();
    }
    // An intercepted local test page exercises the future published state.
    // Only the successful case uses the real browser Clipboard API.
    for (const mode of ['success', 'denied', 'unavailable']) {
      const context = await browser.newContext();
      if (mode === 'success') await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base });
      if (mode !== 'success') await context.addInitScript((mode) => {
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: mode === 'unavailable' ? undefined : { writeText: async () => { throw new DOMException('Test permission denial', 'NotAllowedError'); } } });
      }, mode);
      const page = await context.newPage();
      await page.route('**/__fundraising_test__', r => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: publicationFixture,
        headers: { 'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" } }));
      await page.goto(base + '/__fundraising_test__');
      await page.getByRole('button', { name: '계좌번호 복사' }).click();
      await page.waitForFunction(() => !document.querySelector('[data-copy-fundraising-account]').disabled);
      const result = await page.locator('.fundraising-copy-result').innerText();
      if (mode === 'success') {
        assert.equal(result, '계좌번호를 복사했습니다.');
        assert.equal(await page.evaluate(() => navigator.clipboard.readText()), 'TEST-ACCOUNT-NOT-REAL');
      } else {
        assert.match(result, /복사하지 못했습니다/);
        assert.doesNotMatch(result, /^계좌번호를 복사했습니다/);
      }
      results.push({ publicationFixture: mode, copyResult: 'pass' });
      await context.close();
    }
    fs.writeFileSync(path.join(artifacts, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
