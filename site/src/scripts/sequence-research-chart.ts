import { init, use } from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, AriaComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { selectResearchRows } from '../lib/sequence-research.ts';
import type { ResearchProjection, ModelId } from '../lib/sequence-research.ts';
import type en from '../i18n/sequence-research-en.json';
use([BarChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, MarkLineComponent, CanvasRenderer]);
export type Metric = 'net_return' | 'auc' | 'skill';
export interface SequenceChartController { draw(study:string,metric:Metric):void; resize():void; }
export function createSequenceComparison(plot:HTMLElement,data:ResearchProjection,t:typeof en,locale:string):SequenceChartController {
 const chart=init(plot);
 const formatter=(value:number,metric:Metric)=>metric==='auc'?new Intl.NumberFormat(locale,{maximumFractionDigits:3}).format(value):new Intl.NumberFormat(locale,{style:'percent',maximumFractionDigits:2}).format(value);
 return {
  resize:()=>chart.resize(),
  draw(study,metric){
   const rows=selectResearchRows(data,study);
   const labels=rows.map(r=>t.models[r.model]);
   const fixed:(number|null)[]=rows.map(r=>metric==='auc'?('auc' in r?r.auc:null):metric==='skill'?('skill' in r?r.skill:r.brier_skill):r.net_return);
   const selected:(number|null)[]=rows.map(r=>r.threshold_return);
   if(study==='primary'&&metric==='net_return')for(const [id,value] of [['holding',data.primary.holding_return],['volatility10',data.primary.volatility_return]] as [ModelId,number][]){labels.push(t.models[id]);fixed.push(value);selected.push(null);}
   const style=getComputedStyle(plot),ink=style.color;
   const probe=document.createElement('span');plot.append(probe);
   const color=(name:string)=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
   const green=color('--green'),line=color('--line'),surface=color('--surface'),secondary=color('--ask');probe.remove();
   plot.dataset.chartColors=JSON.stringify({ink,green,secondary});
   plot.dataset.chartSelection=JSON.stringify({study,metric,values:fixed,selected:metric==='net_return'?selected:null});
   chart.setOption({animation:false,backgroundColor:'transparent',textStyle:{color:ink},aria:{enabled:true,label:{description:t.chartTitle}},legend:{type:'scroll',bottom:0,textStyle:{color:ink}},tooltip:{trigger:'axis',renderMode:'richText',backgroundColor:surface,borderColor:line,textStyle:{color:ink},valueFormatter:(value:unknown)=>typeof value==='number'?formatter(value,metric):t.unavailable},grid:{left:70,right:20,top:35,bottom:105},xAxis:{type:'category',data:labels,axisLabel:{color:ink,rotate:15,width:105,overflow:'truncate'}},yAxis:{type:'value',min:metric==='auc'?0:undefined,max:metric==='auc'?1:undefined,axisLabel:{color:ink,formatter:(v:number)=>formatter(v,metric)},splitLine:{lineStyle:{color:line}}},series:[{name:metric==='net_return'?t.fixedSeries:t.metrics[metric],type:'bar',data:fixed,itemStyle:{color:green},markLine:metric==='auc'?{symbol:'none',label:{formatter:t.aucReference,color:ink},lineStyle:{color:secondary,type:'dashed'},data:[{yAxis:.5}]}:undefined},...(metric==='net_return'?[{name:t.selectedSeries,type:'bar',data:selected,itemStyle:{color:secondary}}]:[])]},true);
  }
 };
}
