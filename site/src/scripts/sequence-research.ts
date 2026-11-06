import {validateResearchProjection} from '../lib/sequence-research.ts';
import type {SequenceChartController,Metric} from './sequence-research-chart.ts';
import type en from '../i18n/sequence-research-en.json';
export function mountSequenceResearch(root:HTMLElement):void {
 const payload=JSON.parse(root.querySelector('[data-research-config]')?.textContent||'{}') as {data:unknown;t:typeof en;locale:string};
 const data=validateResearchProjection(payload.data),{t,locale}=payload;
 const route=root.querySelector<HTMLSelectElement>('[data-route]');
 if(route){
  root.querySelector<HTMLElement>('[data-route-controls]')!.hidden=false;
  const update=()=>{
   const sparse=route.value==='sparse';
   root.querySelectorAll<HTMLElement>('[data-expert]').forEach((node,index)=>{const active=!sparse||index<2;node.dataset.active=String(active);node.querySelector<HTMLElement>('[data-expert-status]')!.textContent=active?t.active:t.inactive;});
   root.dataset.routeMode=route.value;
  };
  route.addEventListener('change',update);update();
 }
 const button=root.querySelector<HTMLButtonElement>('[data-research-load]')!,plot=root.querySelector<HTMLElement>('[data-research-chart]')!,study=root.querySelector<HTMLSelectElement>('[data-research-study]')!,metric=root.querySelector<HTMLSelectElement>('[data-research-metric]')!;
 const error=root.querySelector<HTMLElement>('[data-research-error]')!;
 let controller:SequenceChartController|null=null;
 button.hidden=false;root.querySelector<HTMLElement>('[data-research-controls]')!.hidden=false;
 const draw=()=>controller?.draw(study.value,metric.value as Metric);
 study.addEventListener('change',()=>{const option=metric.querySelector<HTMLOptionElement>('option[value="auc"]')!;option.disabled=study.value!=='primary';if(option.disabled&&metric.value==='auc')metric.value='net_return';draw();});metric.addEventListener('change',draw);
 button.addEventListener('click',async()=>{
  button.disabled=true;
  try{const module=await import('./sequence-research-chart.ts');plot.hidden=false;controller=module.createSequenceComparison(plot,data,t,locale);draw();button.hidden=true;const resize=()=>controller?.resize();new ResizeObserver(resize).observe(plot);window.addEventListener('resize',resize);root.dataset.researchReady='true';}
  catch{error.hidden=false;button.disabled=false;plot.hidden=true;}
 });
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);
}
