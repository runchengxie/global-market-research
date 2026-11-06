import { test, expect } from '@playwright/test';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const assets = resolve('../research/equity-lab/src/equity_lab/study/sequence/templates');
const catalogs = Object.fromEntries(['en', 'zh-CN'].map(lang => [lang, JSON.parse(readFileSync(join(assets, `${lang}.json`), 'utf8'))]));
const account = { return: .02, drawdown: -.01, exposure: .5, realized_annual_volatility: .1, equity: [1.01, 1.02], open_exposure: [.5, .5] };
const report = { schema: 'equity_lab.sequence_diagnostics.v1', status: 'completed', provenance: { note: 'SYNTHETIC browser fixture' }, records: ['dense', 'sparse'].map((model, fold) => ({ model, fold, seed: 11, dates: ['2026-01-05', '2026-01-06'], test: { reliability: [{ bin: 5, predicted: .55, observed: .5, count: 2 }] }, accounts: { original: { '5': account }, constant_25: { '5': { ...account, return: .01 } } } })) };
let directory, url;
test.beforeAll(() => {
  directory = mkdtempSync(join(tmpdir(), 'sequence-local-browser-'));
  let html = readFileSync(join(assets, 'viewer.html'), 'utf8');
  const replacements = { DATA_JSON: JSON.stringify(report), CATALOGS: JSON.stringify(catalogs), STATUS: 'completed', PROVENANCE: 'SYNTHETIC browser fixture', FALLBACK_ROWS: '<tr><td>dense</td><td>0</td><td>11</td><td>2.00%</td></tr><tr><td>sparse</td><td>1</td><td>11</td><td>2.00%</td></tr>' };
  for (const [key, value] of Object.entries(replacements)) html = html.replace(`__${key}__`, value);
  for (const [key, value] of Object.entries(catalogs.en)) html = html.replaceAll(`__LABEL_${key}__`, value);
  const path = join(directory, 'browser.html');
  writeFileSync(path, html); url = pathToFileURL(path).href;
});
test.afterAll(() => rmSync(directory, { recursive: true, force: true }));

test('private file browser filters, translates and rejects invalid imported reports without network', async ({ page }) => {
  const requests = []; const errors = [];
  page.on('request', request => { if (/^https?:/.test(request.url())) requests.push(request.url()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await expect(page.locator('[data-count]')).toHaveText('2');
  await expect(page.locator('[data-equity] polyline')).toHaveCount(1);
  await page.locator('[data-filter="model"]').selectOption('sparse');
  await expect(page.locator('[data-count]')).toHaveText('1');
  await page.locator('[data-control]').selectOption('constant_25');
  await expect(page.locator('[data-report-table] tbody')).toContainText('1%');
  await page.locator('[data-lang]').selectOption('zh-CN');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.locator('h1')).toHaveText(catalogs['zh-CN'].title);
  await page.locator('[data-open]').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{"schema":"bad"}') });
  await expect(page.locator('[data-error]')).toBeVisible();
  await expect(page.locator('[data-count]')).toHaveText('1');
  const next = { ...report, status: 'partial', records: [report.records[0]] };
  await page.locator('[data-open]').setInputFiles({ name: 'next.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(next)) });
  await expect(page.locator('[data-status]')).toHaveText('partial');
  await expect(page.locator('[data-error]')).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(requests).toEqual([]); expect(errors).toEqual([]);
});

test('private file retains a useful table with JavaScript disabled', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage(); await page.goto(url);
  await expect(page.locator('[data-report-table] tbody tr')).toHaveCount(2);
  await expect(page.locator('[data-report-table] tbody')).toContainText('2.00%');
  await expect(page.locator('[data-interactive]')).toBeHidden();
  await context.close();
});
