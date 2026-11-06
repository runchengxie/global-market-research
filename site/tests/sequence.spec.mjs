import { test, expect } from '@playwright/test';
for (const locale of ['en','zh-CN']) {
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: sequence synthetic chart and accessible table`,async({page})=>{
  await page.goto(`${prefix}research/lstm-moe/`);
  await expect(page.locator('[data-sequence] table tbody tr')).toHaveCount(12);
  await page.locator('[data-load]').click();
  await expect(page.locator('[data-plot] canvas')).toBeVisible();
  await page.locator('[data-model]').selectOption('sparse');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 });
 test(`${locale}: sequence page remains usable without JS`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  const page=await context.newPage();
  await page.goto(`${prefix}research/lstm-moe/`);
  await expect(page.locator('[data-sequence] table')).toBeVisible();
  await expect(page.locator('[data-sequence] .notice').first()).toBeVisible();
  await context.close();
 });
}

for (const locale of ['en','zh-CN']) {
 test(`${locale}: sequence chart stays contained when resize observers are delayed`,async({page})=>{
  await page.addInitScript(()=>{window.ResizeObserver=class {observe(){} disconnect(){} unobserve(){}};});
  await page.setViewportSize({width:1360,height:1000});
  await page.goto(`/global-market-research/${locale==='en'?'':'zh-CN/'}research/lstm-moe/`);
  await page.locator('[data-load]').click();
  await expect(page.locator('[data-plot] canvas')).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect.poll(()=>page.locator('[data-plot]').evaluate(node=>Math.abs(node.querySelector('canvas').getBoundingClientRect().width-node.clientWidth)<2)).toBe(true);
 });
}
