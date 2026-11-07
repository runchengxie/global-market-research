import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const facts=JSON.parse(readFileSync(new URL('../src/data/crypto-evidence.v1.json',import.meta.url),'utf8'));
for(const locale of ['en','zh-CN']){
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 const t=JSON.parse(readFileSync(new URL(`../src/i18n/crypto-evidence-${locale}.json`,import.meta.url),'utf8'));
 test(`${locale}: measured crypto cases, cost controls, theme and mobile`,async({page},info)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(prefix+'markets/');await page.locator('[data-crypto-evidence-link]').click();await expect(page).toHaveURL(new RegExp('research/crypto-evidence/$'));
  const root=page.locator('[data-crypto-evidence]');expect(await root.locator('[data-crypto-config]').evaluate(n=>JSON.parse(n.textContent).data)).toEqual(facts);
  for(const step of [1,4])await expect(root.locator(`[data-crypto-summary="${step}"] tbody tr`)).toHaveCount(8);
  await expect(root.locator('[data-crypto-folds] tbody tr')).toHaveCount(144);await expect(root.locator('[data-crypto-conclusion]')).toHaveText(t.findings.no_prior_skill);
  await root.locator('[data-crypto-load]').click();await expect(root).toHaveAttribute('data-crypto-ready','true');const plot=root.locator('[data-crypto-chart]');await expect(plot.locator('canvas')).toBeVisible();
  expect(await plot.evaluate(n=>JSON.parse(n.dataset.chartSelection).values)).toEqual(facts.rows.filter(r=>r.step_hours===4&&r.fee_bps===10).map(r=>r.skill));
  await root.locator('[data-crypto-metric]').selectOption('net_return');expect(await plot.evaluate(n=>JSON.parse(n.dataset.chartSelection).series)).toEqual([0,10,25].map(fee=>facts.rows.filter(r=>r.step_hours===4&&r.fee_bps===fee).map(r=>r.net_return)));
  await root.locator('[data-crypto-grain]').selectOption('1');await root.locator('[data-crypto-metric]').selectOption('skill');expect(await plot.evaluate(n=>JSON.parse(n.dataset.chartSelection).values)).toEqual(facts.rows.filter(r=>r.step_hours===1&&r.fee_bps===10).map(r=>r.skill));
  for(const theme of ['dark','light','system']){await page.locator('#theme-preference').selectOption(theme);await expect.poll(()=>plot.evaluate(n=>JSON.parse(n.dataset.chartColors).ink===getComputedStyle(n).color)).toBe(true);if(theme==='dark')await plot.screenshot({path:info.outputPath('crypto-chart-dark.png')});}
  await plot.screenshot({path:info.outputPath('crypto-chart-desktop.png')});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await root.locator('header').screenshot({path:info.outputPath('crypto-mobile.png')});expect(errors).toEqual([]);
 });
 test(`${locale}: full measured facts without JavaScript`,async({browser,baseURL})=>{
  const context=await browser.newContext({javaScriptEnabled:false,baseURL});const page=await context.newPage();await page.goto(prefix+'research/crypto-evidence/');const root=page.locator('[data-crypto-evidence]');await expect(root.locator('[data-crypto-folds] tbody tr')).toHaveCount(144);await expect(root.locator('[data-crypto-load]')).toBeHidden();await expect(root.getByText(t.factorAvailability,{exact:true})).toBeVisible();
  for(const [label,key] of [[t.forecasts,'committed_forecasts'],[t.scored,'scored_forecasts'],[t.observed,'observed_bars']])await expect(root.locator('[data-crypto-forward] div').filter({has:page.getByText(label,{exact:true})}).locator('dd')).toHaveText(new Intl.NumberFormat(locale,{maximumFractionDigits:2}).format(facts.observation[key]));
  await expect(root.getByText(t.unscored,{exact:true})).toBeVisible();await context.close();
 });
}
test('crypto results are embedded beside real LSTM evidence and separate synthetic example',async({page})=>{await page.goto('/global-market-research/zh-CN/research/lstm-moe/');await expect(page.locator('[data-crypto-summary]')).toHaveCount(1);await expect(page.locator('[data-crypto-summary]')).toHaveAttribute('data-crypto-fits','24');await expect(page.locator('[data-crypto-folds]')).toHaveCount(0);await expect(page.locator('[data-crypto-summary] a')).toHaveAttribute('href','/global-market-research/zh-CN/research/crypto-evidence/');await expect(page.locator('[data-primary-results] tbody tr')).toHaveCount(4);await expect(page.locator('[data-synthetic-table] tbody tr')).toHaveCount(12);});
test('crypto chart survives delayed resize observers',async({page})=>{await page.addInitScript(()=>window.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}});await page.goto('/global-market-research/research/crypto-evidence/');const root=page.locator('[data-crypto-evidence]');await root.locator('[data-crypto-load]').click();const plot=root.locator('[data-crypto-chart]');await expect(plot.locator('canvas')).toBeVisible();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect.poll(()=>plot.evaluate(n=>Math.abs(n.querySelector('canvas').getBoundingClientRect().width-n.clientWidth)<2)).toBe(true);});
