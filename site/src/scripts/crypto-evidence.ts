import {validateCryptoEvidence} from '../lib/crypto-evidence.ts';
import type {CryptoChart,CryptoMetric} from './crypto-evidence-chart.ts';
import type en from '../i18n/crypto-evidence-en.json';
export function mountCryptoEvidence(root:HTMLElement):void{
 const config=JSON.parse(root.querySelector('[data-crypto-config]')!.textContent||'{}') as {data:unknown;t:typeof en;locale:string};
 const data=validateCryptoEvidence(config.data),{t,locale}=config;
 const button=root.querySelector<HTMLButtonElement>('[data-crypto-load]')!,plot=root.querySelector<HTMLElement>('[data-crypto-chart]')!,grain=root.querySelector<HTMLSelectElement>('[data-crypto-grain]')!,metric=root.querySelector<HTMLSelectElement>('[data-crypto-metric]')!,error=root.querySelector<HTMLElement>('[data-crypto-error]')!;
 let chart:CryptoChart|null=null;const draw=()=>chart?.draw(Number(grain.value),metric.value as CryptoMetric);
 button.hidden=false;root.querySelector<HTMLElement>('[data-crypto-controls]')!.hidden=false;
 grain.addEventListener('change',draw);metric.addEventListener('change',draw);
 button.addEventListener('click',async()=>{button.disabled=true;try{const module=await import('./crypto-evidence-chart.ts');plot.hidden=false;chart=module.createCryptoChart(plot,data,t,locale);draw();button.hidden=true;root.dataset.cryptoReady='true';const resize=()=>chart?.resize();new ResizeObserver(resize).observe(plot);window.addEventListener('resize',resize);}catch{plot.hidden=true;error.hidden=false;button.disabled=false;}});
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
}
