import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const facts=JSON.parse(readFileSync(new URL('../src/data/sequence-research.v1.json',import.meta.url),'utf8'));
for(const locale of ['en','zh-CN']){
 const path=`/global-market-research/${locale==='en'?'':'zh-CN/'}research/lstm-moe/`;
 const t=JSON.parse(readFileSync(new URL(`../src/i18n/sequence-research-${locale}.json`,import.meta.url),'utf8'));
 test(`${locale}: exact measured facts, architecture, theme and mobile`,async({page},testInfo)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(path);const root=page.locator('[data-research-evidence]');
  await expect(root.locator('[data-primary-results] tbody tr')).toHaveCount(4);
  expect(await root.locator('[data-research-config]').evaluate(n=>JSON.parse(n.textContent).data)).toEqual(facts);
  await root.locator('[data-route]').selectOption('sparse');await expect(root.locator('[data-expert][data-active=true]')).toHaveCount(2);await expect(root.locator('[data-expert][data-active=false]')).toHaveCount(1);
  await root.locator('[data-route]').selectOption('equal');await expect(root.locator('[data-expert][data-active=true]')).toHaveCount(3);
  await root.locator('[data-research-load]').click();await expect(root).toHaveAttribute('data-research-ready','true');const plot=root.locator('[data-research-chart]');await expect(plot.locator('canvas')).toBeVisible();
  await root.locator('[data-research-metric]').selectOption('auc');expect(await plot.evaluate(n=>JSON.parse(n.dataset.chartSelection).values)).toEqual(facts.primary.rows.map(r=>r.auc));
  if(facts.target.status==='completed'){
   await root.locator('[data-research-study]').selectOption('regression');await expect(root.locator('[data-research-metric]')).toHaveValue('net_return');await expect(root.locator('[data-research-metric] option[value=auc]')).toHaveJSProperty('disabled',true);
   expect(await plot.evaluate(n=>JSON.parse(n.dataset.chartSelection).values)).toEqual(facts.target.rows.filter(r=>r.objective==='regression').map(r=>r.net_return));
  }
  for(const theme of ['dark','light','system']){await page.locator('#theme-preference').selectOption(theme);await expect.poll(()=>plot.evaluate(n=>JSON.parse(n.dataset.chartColors).ink===getComputedStyle(n).color)).toBe(true);}
  await plot.screenshot({path:testInfo.outputPath('measured-chart-desktop.png')});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect(root.getByText(t.exposureWarning,{exact:true})).toBeVisible();expect(errors).toEqual([]);await root.locator('.architecture-diagram').screenshot({path:testInfo.outputPath('architecture-mobile.png')});
 });
 test(`${locale}: all measured facts without JavaScript`,async({browser,baseURL})=>{
  const context=await browser.newContext({javaScriptEnabled:false,baseURL});const page=await context.newPage();await page.goto(path);await expect(page.locator('[data-primary-results] tbody tr')).toHaveCount(4);await expect(page.locator('[data-exploration]')).toHaveCount(6);await expect(page.getByText(t.conclusion,{exact:true})).toBeVisible();
  if(facts.target.status==='completed')for(const objective of ['classification','regression'])await expect(page.locator(`[data-target-results=${objective}] tbody tr`)).toHaveCount(5);
  await expect(page.locator('[data-research-load]')).toBeHidden();await expect(page.locator('[data-synthetic-table] tbody tr')).toHaveCount(12);await context.close();
 });
}
test('research chart with delayed resize observers',async({page})=>{
 await page.addInitScript(()=>{window.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};});await page.setViewportSize({width:1360,height:1000});await page.goto('/global-market-research/research/lstm-moe/');const root=page.locator('[data-research-evidence]');await root.locator('[data-research-load]').click();await expect(root.locator('canvas')).toBeVisible();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect.poll(()=>root.locator('[data-research-chart]').evaluate(n=>Math.abs(n.querySelector('canvas').getBoundingClientRect().width-n.clientWidth)<2)).toBe(true);
});
