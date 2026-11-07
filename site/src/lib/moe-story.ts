/** Handcrafted educational examples. No research data, trained parameters or inference. */
export type Mode='dense'|'equal'|'sparse';
export const STEPS=10;
export const SCENARIOS=[
 {changes:[-.8,.4,1.2,-.3,.7],logits:[1.1,.4,-.3],representations:[[.8,.2],[.2,.7],[-.4,.5]]},
 {changes:[.5,-1.1,.3,.6,-.2],logits:[.2,1,.6],representations:[[.1,.8],[.7,.1],[.3,-.2]]},
 {changes:[-.3,.8,-.6,.2,1],logits:[-.2,.5,1.2],representations:[[-.2,.4],[.2,-.1],[.6,.5]]},
] as const;
export interface Frame {phase:'input'|'route'|'dispatch'|'read'|'mix'|'output';day:number|null}
function integer(x:number,n:number):void {if(!Number.isInteger(x)||x<0||x>=n)throw new Error('Invalid illustration state');}
export function frame(index:number):Frame{
 integer(index,STEPS);
 if(index>=3&&index<=7)return {phase:'read',day:index-3};
 return {phase:index===0?'input':index===1?'route':index===2?'dispatch':index===8?'mix':'output',day:null};
}
export function advance(index:number):number{frame(index);return Math.min(STEPS-1,index+1);}
export function example(mode:Mode,scenario:number){
 integer(scenario,SCENARIOS.length);if(!['dense','equal','sparse'].includes(mode))throw new Error('Invalid illustration mode');
 const data=SCENARIOS[scenario],max=Math.max(...data.logits),exp=data.logits.map(x=>Math.exp(x-max)),sum=exp.reduce((a,b)=>a+b,0);
 const probabilities=exp.map(x=>x/sum);
 const selected=mode==='sparse'?[0,1,2].sort((a,b)=>probabilities[b]-probabilities[a]).slice(0,2):[0,1,2];
 const selectedSum=selected.reduce((s,i)=>s+probabilities[i],0);
 const weights=probabilities.map((p,i)=>mode==='equal'?1/3:mode==='sparse'?(selected.includes(i)?p/selectedSum:0):p);
 const representations=data.representations.map(v=>[...v]);
 const mixture=[0,1].map(j=>weights.reduce((s,w,i)=>s+w*representations[i][j],0));
 return {weights,selected,representations,mixture,score:.7*mixture[0]-.4*mixture[1]};
}
export function memoryStep(scenario:number,expert:number,day:number){
 integer(scenario,SCENARIOS.length);integer(expert,3);integer(day,5);
 let cell=0;const sigmoid=(x:number)=>1/(1+Math.exp(-x));
 let value={previous:0,forget:0,write:0,candidate:0,cell:0,output:0,hidden:0};
 for(let i=0;i<=day;i++){
  const change=SCENARIOS[scenario].changes[i];
  const previous=cell,forget=sigmoid(.3+change*.1+expert*.1),write=sigmoid(-.1+change*.2-expert*.1),output=sigmoid(.2+change*.05),candidate=Math.tanh(change/2+expert*.1);
  cell=forget*previous+write*candidate;
  value={previous,forget,write,candidate,cell,output,hidden:output*Math.tanh(cell)};
 }
 return value;
}
