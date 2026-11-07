import {test,expect} from '@playwright/test';
for(const locale of ['en','zh-CN']){
 const path=`/global-market-research/${locale==='en'?'':'zh-CN/'}research/crypto-evidence/`;
 test(`${locale}: research journal shows real follow-up and folds`,async({page},info)=>{
  await page.goto(path);const root=page.locator('[data-crypto-followup]');await expect(root).toHaveAttribute('data-fit-count','39');
  await expect(root.locator('[data-followup-models] tbody tr')).toHaveCount(5);await expect(root.locator('[data-followup-cash] tbody tr')).toHaveCount(6);
  await root.locator('[data-followup-details] summary').click();await expect(root.locator('[data-followup-folds] tbody tr')).toHaveCount(234);
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await root.locator('header').screenshot({path:info.outputPath('journal-mobile.png')});
 });
 test(`${locale}: journal works without scripts`,async({browser,baseURL})=>{
  const context=await browser.newContext({javaScriptEnabled:false,baseURL});const page=await context.newPage();await page.goto(path);const root=page.locator('[data-crypto-followup]');await expect(root).toBeVisible();await expect(root.locator('[data-followup-models] tbody tr')).toHaveCount(5);await expect(root.locator('[data-followup-sources] code')).toHaveCount(5);await context.close();
 });
}
