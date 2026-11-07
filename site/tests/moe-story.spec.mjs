import {test,expect} from '@playwright/test';
for(const locale of ['en','zh-CN']){
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: step through recurrent experts, modes and motion`,async({page},info)=>{
  await page.emulateMedia({reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(prefix+'research/moe-architecture/');
  const root=page.locator('[data-moe-story]');await expect(root).toHaveAttribute('data-ready','true');await expect(root.locator('[data-play]')).toBeDisabled();
  await root.locator('[data-mode]').selectOption('sparse');await root.locator('[data-scenario]').selectOption('2');
  await root.locator('[data-expert-lens="2"]').click();await expect(root).toHaveAttribute('data-step','3');await root.locator('[data-lens-jump="4"]').click();await expect(root).toHaveAttribute('data-day','4');
  await root.locator('[data-jump="4"]').click();await expect(root).toHaveAttribute('data-day','1');await expect(root.locator('[data-story-expert][data-active=true]')).toHaveCount(2);await expect(root.locator('[data-story-expert="2"]')).toHaveAttribute('data-active','true');await expect(root.locator('[data-story-expert="0"] [data-expert-lens]')).toBeDisabled();
  await root.locator('[data-jump="9"]').click();await expect(root.locator('[data-output]')).not.toHaveText('—');
  await root.locator('[data-mode]').selectOption('equal');await expect(root).toHaveAttribute('data-step','0');await expect(root.locator('[data-story-expert][data-active=true]')).toHaveCount(3);await expect(root.locator('[data-weight]').first()).toHaveText(/33/);
  await page.emulateMedia({reducedMotion:'no-preference'});await root.locator('[data-play]').click();await expect(root).toHaveAttribute('data-motion','running');await root.locator('[data-play]').click();const step=await root.getAttribute('data-step');await page.waitForTimeout(2500);await expect(root).toHaveAttribute('data-step',step);
  await root.locator('[data-play]').click();await page.emulateMedia({reducedMotion:'reduce'});await expect(root).toHaveAttribute('data-motion','paused');
  for(const theme of ['dark','light']){await page.locator('#theme-preference').selectOption(theme);await root.locator('[data-diagram]').screenshot({path:info.outputPath(`diagram-${theme}.png`)});}
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await root.locator('[data-diagram]').screenshot({path:info.outputPath('diagram-mobile.png')});expect(errors).toEqual([]);
 });
 test(`${locale}: static explanation and contextual research links`,async({browser,baseURL,page})=>{
  const context=await browser.newContext({javaScriptEnabled:false,baseURL});const offline=await context.newPage();await offline.goto(prefix+'research/moe-architecture/');await expect(offline.locator('[data-story-expert]')).toHaveCount(3);await expect(offline.locator('[data-static-steps] li')).toHaveCount(6);await expect(offline.locator('[data-story-controls]')).toBeHidden();await context.close();
  for(const route of ['lstm-moe','crypto-cnn','crypto-evidence']){await page.goto(prefix+`research/${route}/`);await expect(page.locator('[data-architecture-link]')).toHaveAttribute('href',prefix+'research/moe-architecture/');}
 });
}
test('missing observers still permit manual explanation',async({page})=>{
 await page.addInitScript(()=>{window.IntersectionObserver=undefined;window.ResizeObserver=undefined;});await page.goto('/global-market-research/research/moe-architecture/');const root=page.locator('[data-moe-story]');await expect(root).toHaveAttribute('data-motion','paused');await root.locator('[data-next]').click();await expect(root).toHaveAttribute('data-step','1');
});
test('autoplay runs once, stops at final frame and stays paused offscreen',async({page})=>{
 await page.clock.install();await page.goto('/global-market-research/research/moe-architecture/');const root=page.locator('[data-moe-story]');await root.locator('[data-diagram]').scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-motion','running');await page.clock.runFor(20000);await expect(root).toHaveAttribute('data-step','9');await expect(root).toHaveAttribute('data-motion','paused');await root.locator('[data-restart]').click();await root.locator('[data-play]').click();await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await expect(root).toHaveAttribute('data-motion','paused');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-motion','paused');
});
test('hidden document pauses an active story without resuming automatically',async({page})=>{
 await page.goto('/global-market-research/research/moe-architecture/');const root=page.locator('[data-moe-story]');await root.locator('[data-diagram]').scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-motion','running');
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});await expect(root).toHaveAttribute('data-motion','paused');
 await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});await expect(root).toHaveAttribute('data-motion','paused');
});
