import type snapshot from '../data/crypto-followup.v1.json';
export type CryptoFollowup=typeof snapshot;
const kinds=['ridge','single','matched','equal','dense'];
const fail=():never=>{throw new Error('Invalid crypto follow-up evidence');};
function record(x:unknown):Record<string,unknown>{if(!x||typeof x!=='object'||Array.isArray(x))fail();return x as Record<string,unknown>;}
function keys(x:unknown,names:string[]):Record<string,unknown>{const r=record(x);if(Object.keys(r).length!==names.length||Object.keys(r).some(k=>!names.includes(k)))fail();return r;}
function array(x:unknown):unknown[]{if(!Array.isArray(x))fail();return x as unknown[];}
function numeric(x:unknown):number{if(typeof x!=='number'||!Number.isFinite(x))fail();return x as number;}
function numericTree(x:unknown):void{if(x===null)return;if(typeof x==='number'){numeric(x);return;}if(typeof x==='string')return;if(Array.isArray(x)){x.forEach(numericTree);return;}Object.values(record(x)).forEach(numericTree);}
function oneOf(x:unknown,allowed:unknown[]):void{if(!allowed.includes(x))fail();}
export function validateCryptoFollowup(input:unknown):CryptoFollowup{
 const x=keys(input,['schema','as_of','scope','sources','forward','diagnostics','comparison','provider']);
 oneOf(x.schema,['crypto.followup_public.v1']);oneOf(x.scope,['retrospective_exploration_not_fresh_holdout']);
 const sources=keys(x.sources,['audit','diagnostics','comparison','plan','projection_code']);for(const h of Object.values(sources))if(typeof h!=='string'||!(/^[a-f0-9]{64}$/).test(h))fail();
 const f=keys(x.forward,['as_of','prefix_head','prefix_receipts','committed','scored','pending','mature_unscored','observed_bars','revisions','late_received_bars','mse','prior_mse','skill','deadline_violations','score_reconstruction_violations']);
 for(const date of [x.as_of,f.as_of])if(typeof date!=='string'||!Number.isFinite(Date.parse(date)))fail();
 if(Date.parse(String(f.as_of))>Date.parse(String(x.as_of))||!(/^[a-f0-9]{64}$/).test(String(f.prefix_head)))fail();
 for(const k of ['prefix_receipts','committed','scored','pending','mature_unscored','observed_bars','revisions','late_received_bars','deadline_violations','score_reconstruction_violations'])if(!Number.isInteger(numeric(f[k]))||numeric(f[k])<0)fail();
 if(f.committed!==numeric(f.scored)+numeric(f.pending)+numeric(f.mature_unscored)||f.deadline_violations!==0||f.score_reconstruction_violations!==0)fail();
 const d=keys(x.diagnostics,['quantile_levels','hurdles','rows']);if(JSON.stringify(d.quantile_levels)!=='[0,0.01,0.1,0.5,0.9,0.99,1]'||JSON.stringify(d.hurdles)!=='[0,0.001,0.002]'||array(d.rows).length!==30)fail();
 for(const item of array(d.rows)){const r=keys(item,['step_hours','fold','model','count','prediction_quantiles','target_quantiles','above_hurdles']);if(!Number.isInteger(numeric(r.count))||numeric(r.count)<=0)fail();oneOf(r.step_hours,[1,4]);oneOf(r.fold,[0,1,2]);oneOf(r.model,['price_only','prior','factor_proxy_24h','factor_delayed_72h','factor_shift_7d']);for(const k of ['prediction_quantiles','target_quantiles','above_hurdles']){const values=array(r[k]).map(numeric);if(values.length!==(k==='above_hurdles'?3:7))fail();if(k==='above_hurdles'?values.some(v=>v<0||v>1):values.some((v,i)=>i>0&&v<values[i-1]))fail();}}
 for(const key of ['mse','prior_mse','skill'])if(f[key]!==null)numeric(f[key]);
 const c=keys(x.comparison,['status','fits_started','fits_completed','elapsed_seconds','architecture','rows','aggregates','gates','source_revision']);oneOf(c.status,['completed']);if(c.fits_started!==39||c.fits_completed!==39||numeric(c.elapsed_seconds)<0||numeric(c.elapsed_seconds)>=900||array(c.rows).length!==234||array(c.aggregates).length!==30||array(c.gates).length!==36)fail();
 Object.values(keys(c.architecture,kinds)).forEach(numeric);if(!(/^[a-f0-9]{40}$/).test(String(c.source_revision)))fail();
 const ids=new Set<string>();
 for(const item of array(c.rows)){const r=keys(item,['fold','kind','seed','rule','hurdle','fee_bps','mse','skill','parameters','fit_samples','validation_samples','test_samples','net_return','exposure','turnover','max_drawdown']);for(const [key,value] of Object.entries(r))if(!['kind','rule'].includes(key)&&value!==null)numeric(value);oneOf(r.kind,kinds);oneOf(r.rule,['fixed','validation']);oneOf(r.hurdle,[0,.001,.002]);oneOf(r.fee_bps,[0,10,25]);oneOf(r.fold,[0,1,2]);oneOf(r.seed,r.kind==='ridge'?[0]:[11,29,47]);if(r.rule==='fixed'&&r.hurdle!==.002)fail();if(numeric(r.exposure)<0||numeric(r.exposure)>1||numeric(r.max_drawdown)>0||numeric(r.max_drawdown)<-1)fail();const id=[r.fold,r.kind,r.seed,r.rule,r.fee_bps].join(':');if(ids.has(id))fail();ids.add(id);}
 for(const item of array(c.aggregates)){const r=keys(item,['kind','rule','fee_bps','cases','net_return','min_return','max_return','skill','exposure','turnover','max_drawdown']);for(const [key,value] of Object.entries(r))if(!['kind','rule'].includes(key)&&value!==null)numeric(value);oneOf(r.kind,kinds);oneOf(r.rule,['fixed','validation']);oneOf(r.fee_bps,[0,10,25]);}
 for(const item of array(c.gates)){const r=keys(item,['fold','kind','seed','mean_weights','entropy']);oneOf(r.kind,kinds.slice(1));oneOf(r.fold,[0,1,2]);oneOf(r.seed,[11,29,47]);if(numeric(r.entropy)<0)fail();const g=array(r.mean_weights).map(numeric);if(g.length!==(r.kind==='dense'||r.kind==='equal'?3:1)||g.some(v=>v<0||v>1)||Math.abs(g.reduce((a,b)=>a+b,0)-1)>1e-4)fail();}
 const p=keys(x.provider,['reviewed_on','definitions','historical_availability','revision_policy']);oneOf(p.reviewed_on,['2026-11-07']);oneOf(p.historical_availability,['unverified']);oneOf(p.revision_policy,['unverified']);const defs=keys(p.definitions,['CO-A-02-03','CO-S-01-01','CO-S-01-05']);oneOf(defs['CO-A-02-03'],['documented']);oneOf(defs['CO-S-01-01'],['documented']);oneOf(defs['CO-S-01-05'],['unverified']);numericTree(x);
 return x as unknown as CryptoFollowup;
}
