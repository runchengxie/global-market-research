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
