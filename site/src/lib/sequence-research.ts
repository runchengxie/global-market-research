export type Objective = 'classification' | 'regression';
export type ModelId = 'prior' | 'linear' | 'matched' | 'equal' | 'dense' | 'sparse' | 'holding' | 'volatility10';
export interface CommonRow { model: ModelId; cases: number; net_return: number; threshold_return: number; exposure: number; threshold_exposure: number; }
export interface PrimaryRow extends CommonRow { flat: number; auc: number; brier_skill: number; daily_difference: number; daily_interval: [number, number]; }
export interface TargetRow extends CommonRow { objective: Objective; skill: number | null; ic: number | null; volatility: number; }
export type ResearchRow = PrimaryRow | TargetRow;
export type GateStatus = 'continue_deferred' | 'promising_retrospective' | 'insufficient_evidence';
export type ExplorationId = 'primary' | 'checkpoint' | 'diagnostics' | 'targets' | 'transformer' | 'crypto';
export interface ResearchProjection {
 schema: 'sequence_research_public.v1'; scope: 'retrospective_aggregate_only'; accepted_research: false; execution_authorized: false;
 sample: { stocks:number; sessions:number; start:string; end:string; currency:string; price_basis:string; dividends:false; fixed_current:true; previously_exposed:true };
 architecture: { lookback:number; features:number; experts:number; units:number; top_k:number; representation:number; parameters:number; matched_units:number; matched_parameters:number; router_context:string; mix:string };
 primary: { folds:number; seeds:number; cases:number; fee_bps:number; rows:PrimaryRow[]; holding_return:number; volatility_return:number };
 target: { status:'pending'|'completed'; folds:number; seeds:number; cases:number; fits:number; epochs:number; batch_size:number; rows:TargetRow[]; continuation:{objective:Objective;status:GateStatus;passed_checks:number;total_checks:number}[] };
 explorations: {id:ExplorationId;status:'completed'|'pending'|'planned';cases:number;fits:number}[];
 source_revisions: {primary:string;diagnostics:string;target:string|null;analysis:string|null};
}
const fail=(): never=>{throw new Error('Invalid aggregate sequence research projection');};
function keys(value: unknown,allowed: readonly string[]){if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).length!==allowed.length||Object.keys(value).some(k=>!allowed.includes(k)))fail();}
const integer=(v: number,min=0)=>{if(!Number.isInteger(v)||v<min)fail();};
const finite=(v: number|null,nullable=false)=>{if(nullable&&v===null)return;if(!Number.isFinite(v))fail();};
const fraction=(v: number)=>{finite(v);if(v<0||v>1+1e-9)fail();};
const unique=(rows: readonly {objective?:string;model:string}[])=>{if(new Set(rows.map(r=>(r.objective||'')+r.model)).size!==rows.length)fail();};
export function validateResearchProjection(input: unknown): ResearchProjection {
 // Boundary cast is used only for field inspection; return occurs after runtime validation.
 const d=input as ResearchProjection;
 keys(d,['schema','scope','accepted_research','execution_authorized','sample','architecture','primary','target','explorations','source_revisions']);
 if(d.schema!=='sequence_research_public.v1'||d.scope!=='retrospective_aggregate_only'||d.accepted_research!==false||d.execution_authorized!==false)fail();
 keys(d.sample,['stocks','sessions','start','end','currency','price_basis','dividends','fixed_current','previously_exposed']);
 integer(d.sample.stocks,1);integer(d.sample.sessions,1);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(d.sample.start)||!/^\d{4}-\d{2}-\d{2}$/.test(d.sample.end)||d.sample.start>=d.sample.end||d.sample.currency!=='USD'||d.sample.price_basis!=='split_adjusted'||d.sample.dividends!==false||d.sample.fixed_current!==true||d.sample.previously_exposed!==true)fail();
 keys(d.architecture,['lookback','features','experts','units','top_k','representation','parameters','matched_units','matched_parameters','router_context','mix']);
 for(const k of (['lookback','features','experts','units','top_k','representation','parameters','matched_units','matched_parameters'] as const))integer(d.architecture[k],1);
 if(d.architecture.lookback!==20||d.architecture.features!==10||d.architecture.experts!==3||d.architecture.units!==64||d.architecture.top_k!==2||d.architecture.parameters!==59682||d.architecture.matched_units!==114||d.architecture.matched_parameters!==59748||d.architecture.top_k>=d.architecture.experts||d.architecture.representation!==d.architecture.lookback*d.architecture.units||d.architecture.router_context!=='last_feature_row'||d.architecture.mix!=='hidden_representation')fail();
 keys(d.primary,['folds','seeds','cases','fee_bps','rows','holding_return','volatility_return']);
 if(d.primary.folds!==7||d.primary.seeds!==5||d.primary.cases!==350||d.primary.fee_bps!==5||!Array.isArray(d.primary.rows)||d.primary.rows.length!==4)fail();
 finite(d.primary.holding_return);finite(d.primary.volatility_return);unique(d.primary.rows);
 for(const r of d.primary.rows){keys(r,['model','cases','flat','auc','brier_skill','net_return','threshold_return','exposure','threshold_exposure','daily_difference','daily_interval']);if(!['matched','equal','dense','sparse'].includes(r.model))fail();integer(r.cases,1);integer(r.flat);if(r.flat>r.cases||r.cases!==35)fail();fraction(r.auc);fraction(r.exposure);fraction(r.threshold_exposure);for(const k of (['brier_skill','net_return','threshold_return','daily_difference'] as const))finite(r[k]);if(!Array.isArray(r.daily_interval)||r.daily_interval.length!==2||r.daily_interval.some(v=>!Number.isFinite(v))||r.daily_interval[0]>r.daily_interval[1])fail();}
 keys(d.target,['status','folds','seeds','cases','fits','epochs','batch_size','rows','continuation']);
 if(!['pending','completed'].includes(d.target.status)||d.target.folds!==7||d.target.seeds!==3||d.target.epochs!==30||d.target.batch_size!==128||!Array.isArray(d.target.rows)||!Array.isArray(d.target.continuation))fail();
 unique(d.target.rows);integer(d.target.cases);integer(d.target.fits);
 if(new Set(d.target.continuation.map(r=>r.objective)).size!==d.target.continuation.length)fail();
 if(d.target.status==='completed'&&(d.target.cases!==175||d.target.fits!==140||d.target.rows.length!==10||d.target.continuation.length!==2))fail();
 if(d.target.status==='pending'&&(d.target.cases!==0||d.target.fits!==0||d.target.rows.length||d.target.continuation.length))fail();
 for(const r of d.target.rows){keys(r,['objective','model','cases','skill','ic','net_return','threshold_return','exposure','threshold_exposure','volatility']);if(!['classification','regression'].includes(r.objective)||!['prior','linear','matched','equal','sparse'].includes(r.model))fail();integer(r.cases,1);if(r.cases!==(['prior','linear'].includes(r.model)?7:21))fail();finite(r.skill,true);finite(r.ic,true);if(r.ic!==null&&Math.abs(r.ic)>1+1e-9)fail();for(const k of (['net_return','threshold_return','volatility'] as const))finite(r[k]);fraction(r.exposure);fraction(r.threshold_exposure);}
 for(const r of d.target.continuation){keys(r,['objective','status','passed_checks','total_checks']);if(!['classification','regression'].includes(r.objective)||!['continue_deferred','promising_retrospective','insufficient_evidence'].includes(r.status))fail();integer(r.passed_checks);integer(r.total_checks);if(r.passed_checks>r.total_checks)fail();}
 if(!Array.isArray(d.explorations)||d.explorations.length!==6||new Set(d.explorations.map(r=>r.id)).size!==6)fail();
 for(const r of d.explorations){keys(r,['id','status','cases','fits']);if(!['primary','checkpoint','diagnostics','targets','transformer','crypto'].includes(r.id)||!['completed','pending','planned'].includes(r.status))fail();integer(r.cases);integer(r.fits);}
 keys(d.source_revisions,['primary','diagnostics','target','analysis']);for(const [k,v] of Object.entries(d.source_revisions))if(!(['target','analysis'].includes(k)&&d.target.status==='pending'&&v===null)&&(typeof v!=='string'||!/^[a-f0-9]{7,40}$/.test(v)))fail();
 return d;
}
export function selectResearchRows(data: ResearchProjection,selection: string): ResearchRow[]{validateResearchProjection(data);if(selection==='primary')return data.primary.rows;if(!['classification','regression'].includes(selection))throw Error('Unknown sequence study');return data.target.rows.filter(r=>r.objective===selection);}
