import {advance,example,frame,memoryStep,SCENARIOS,STEPS} from '../lib/moe-story';
import type {Mode} from '../lib/moe-story';
import type en from '../i18n/moe-story-en.json';
/** Motion is an explanation of handcrafted values, never a trained forward pass. */
export function mountMoeStory(root:HTMLElement):void{
 const payload=JSON.parse(root.querySelector('[data-moe-config]')?.textContent||'{}') as {t:typeof en;locale:string};
 const {t,locale}=payload;
 const get=<T extends Element=HTMLElement>(selector:string):T=>{const node=root.querySelector<T>(selector);if(!node)throw new Error('Incomplete MoE illustration');return node;};
 const text=(selector:string,value:string)=>{get(selector).textContent=value;};
 const pct=(x:number)=>new Intl.NumberFormat(locale,{style:'percent',maximumFractionDigits:1}).format(x);
 const num=(x:number)=>new Intl.NumberFormat(locale,{maximumFractionDigits:2,signDisplay:'exceptZero'}).format(x);
 const fill=(s:string,n:number)=>s.replace('{day}',String(n));
 const diagram=get<HTMLElement>('[data-diagram]'),play=get<HTMLButtonElement>('[data-play]'),modeSelect=get<HTMLSelectElement>('[data-mode]'),scenarioSelect=get<HTMLSelectElement>('[data-scenario]');
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let index=0,mode:Mode='dense',scenario=0,lens=0,playing=false,timer:number|undefined,autoAttempted=false,observer:IntersectionObserver|undefined;
 const visible=()=>{const r=diagram.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight;};
 function paint(announce=false):void{
  const f=frame(index),data=example(mode,scenario);
  if(!data.selected.includes(lens))lens=data.selected[0];
  root.dataset.step=String(index);root.dataset.phase=f.phase;root.dataset.day=String(f.day??-1);root.dataset.mode=mode;root.dataset.motion=playing?'running':'paused';
  play.textContent=playing?t.pause:t.play;play.setAttribute('aria-pressed',String(playing));play.disabled=reduced.matches;
  get<HTMLButtonElement>('[data-previous]').disabled=index===0;get<HTMLButtonElement>('[data-next]').disabled=index===STEPS-1;
  text('[data-counter]',t.stepCounter.replace('{current}',String(index+1)).replace('{total}',String(STEPS)));
  text('[data-chapter-index]',String(index+1));text('[data-motion-note]',reduced.matches?t.motionNote:t.manualNote);
  const caption=t.captions[f.phase];const title=fill(caption.title,(f.day??0)+1);
  text('[data-caption-title]',title);text('[data-caption]',caption.body);
  if(announce)text('[data-announcement]',title);
  root.querySelectorAll<HTMLButtonElement>('[data-jump]').forEach((node,i)=>{if(i===index)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');});
  root.querySelectorAll<HTMLElement>('[data-story-day]').forEach((node,i)=>{
   node.dataset.current=String(f.phase==='read'&&f.day===i||f.phase==='route'&&i===4);
   node.querySelector<HTMLElement>('[data-change]')!.textContent=`${num(SCENARIOS[scenario].changes[i])}%`;
  });
  text('[data-router-title]',mode==='equal'?t.fixedRouter:t.router);text('[data-router-note]',mode==='equal'?t.equalNote:t.routerNote);
  root.querySelectorAll<HTMLElement>('[data-story-expert]').forEach((node,i)=>{
   const active=data.selected.includes(i);node.dataset.active=String(active);node.dataset.reading=String(active&&f.phase==='read');
   node.querySelector<HTMLElement>('[data-expert-status]')!.textContent=!active?t.skipped:f.phase==='read'?fill(t.reading,f.day!+1):index>=8?t.complete:t.waiting;
   node.querySelector<HTMLElement>('[data-weight]')!.textContent=pct(data.weights[i]);node.querySelector<HTMLElement>('[data-weight-bar]')!.style.width=`${data.weights[i]*100}%`;
   node.querySelector<HTMLElement>('[data-notes]')!.textContent=!active?'—':index>=8?`[${data.representations[i].map(num).join(', ')}, …]`:'[ … ]';
   const button=node.querySelector<HTMLButtonElement>('[data-expert-lens]')!;button.hidden=false;button.disabled=!active;button.setAttribute('aria-pressed',String(i===lens));
   get<SVGElement>(`[data-flow-in="${i}"]`).dataset.active=String(active&&index>=2&&index<=7);
   get<SVGElement>(`[data-flow-out="${i}"]`).dataset.active=String(active&&index>=8);
  });
  text('[data-mixture]',index>=8?`[${data.mixture.map(num).join(', ')}, …]`:'[ … ]');text('[data-output]',index===9?num(data.score):'—');
  text('[data-lens-name]',t.expert.replace('{letter}',['A','B','C'][lens]));
  const day=f.day??(index>=8?4:null);
  text('[data-memory-prompt]',day===null?t.memoryStart:fill(t.timeLabel,day+1));
  const memory=day===null?null:memoryStep(scenario,lens,day);
  for(const key of ['forget','write','output'] as const){text(`[data-gate-value="${key}"]`,memory?pct(memory[key]):'—');get<HTMLElement>(`[data-gate-bar="${key}"]`).style.width=memory?`${memory[key]*100}%`:'0%';}
  root.querySelectorAll<HTMLButtonElement>('[data-lens-jump]').forEach((node,i)=>{if(day===i)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');});
  for(const key of ['previous','cell','hidden'] as const)text(`[data-memory-value="${key}"]`,memory?num(memory[key]):'—');
 }
 function stop():void{if(timer!==undefined){clearInterval(timer);timer=undefined;}playing=false;paint();}
 function start():void{
  if(reduced.matches||document.hidden||!visible())return;
  if(index===STEPS-1)index=0;
  if(timer!==undefined)clearInterval(timer);
  playing=true;paint();
  timer=window.setInterval(()=>{
   if(reduced.matches||document.hidden||!visible()){stop();return;}
   index=advance(index);if(index===STEPS-1){stop();return;}paint();
  },2000);
 }
 function manual(next:number):void{autoAttempted=true;stop();index=next;paint(true);}
 play.addEventListener('click',()=>{
  autoAttempted=true;
  if(playing)stop();else{if(!visible())diagram.scrollIntoView({block:'nearest',behavior:'instant'});start();}
 });
 get('[data-previous]').addEventListener('click',()=>manual(Math.max(0,index-1)));
 get('[data-next]').addEventListener('click',()=>manual(advance(index)));
 get('[data-restart]').addEventListener('click',()=>manual(0));
 root.querySelectorAll<HTMLButtonElement>('[data-jump]').forEach(node=>node.addEventListener('click',()=>manual(Number(node.dataset.jump))));
 modeSelect.addEventListener('change',()=>{mode=modeSelect.value as Mode;manual(0);});
 scenarioSelect.addEventListener('change',()=>{scenario=Number(scenarioSelect.value);manual(0);});
 root.querySelectorAll<HTMLButtonElement>('[data-expert-lens]').forEach((node,i)=>node.addEventListener('click',()=>{
  if(!example(mode,scenario).selected.includes(i))return;
  autoAttempted=true;stop();lens=i;if(index<3)index=3;paint(true);get('.memory-lens').scrollIntoView({block:'start',behavior:'instant'});
 }));
 root.querySelectorAll<HTMLButtonElement>('[data-lens-jump]').forEach((node,i)=>node.addEventListener('click',()=>manual(i+3)));
 const preference=()=>{if(reduced.matches){autoAttempted=true;stop();}else paint();};
 const visibility=()=>{if(document.hidden&&playing){autoAttempted=true;stop();}};
 const scroll=()=>{if(playing&&!visible()){autoAttempted=true;stop();}};
 reduced.addEventListener('change',preference);document.addEventListener('visibilitychange',visibility);window.addEventListener('scroll',scroll,{passive:true});
 const pagehide=(event:PageTransitionEvent)=>{
  stop();
  if(!event.persisted){observer?.disconnect();reduced.removeEventListener('change',preference);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('scroll',scroll);window.removeEventListener('pagehide',pagehide);}
 };
 window.addEventListener('pagehide',pagehide);
 get('[data-lens-controls]').hidden=false;get('[data-story-controls]').hidden=false;paint();root.dataset.ready='true';
 if(typeof IntersectionObserver!=='undefined'){
  observer=new IntersectionObserver(entries=>{
   if(!entries[0].isIntersecting){if(playing){autoAttempted=true;stop();}return;}
   if(!autoAttempted&&!reduced.matches&&!document.hidden){autoAttempted=true;start();}
  },{threshold:0});observer.observe(diagram);
 }
}
