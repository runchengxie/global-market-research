import {init,use} from 'echarts/core';
import {BarChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
import {selectCryptoRows} from '../lib/crypto-evidence.ts';
import type {CryptoEvidence} from '../lib/crypto-evidence.ts';
import type en from '../i18n/crypto-evidence-en.json';
use([BarChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,CanvasRenderer]);
export type CryptoMetric=keyof typeof en.metrics;
export interface CryptoChart{draw(step:number,metric:CryptoMetric):void;resize():void}
export function createCryptoChart(plot:HTMLElement,data:CryptoEvidence,t:typeof en,locale:string):CryptoChart{
 const chart=init(plot);
 const format=(value:number,metric:CryptoMetric)=>metric==='turnover'?new Intl.NumberFormat(locale,{maximumFractionDigits:2}).format(value)+'×':new Intl.NumberFormat(locale,{style:'percent',maximumFractionDigits:3}).format(value);
 return {resize:()=>chart.resize(),draw(step,metric){
  const rows=selectCryptoRows(data,step,10),labels=rows.map(r=>t.arms[r.arm]),fees=metric==='net_return'?[0,10,25]:[10];
  const ink=getComputedStyle(plot).color,probe=document.createElement('span');plot.append(probe);
  const color=(name:string)=>{probe.style.color=`var(${name})`;return getComputedStyle(probe).color;};
  const colors=[color('--green'),color('--ask'),color('--bid')],surface=color('--surface'),line=color('--line');probe.remove();
  const series=fees.map((fee,index)=>({name:metric==='net_return'?t.feeSeries.replace('{fee}',String(fee)):t.metrics[metric],type:'bar' as const,data:selectCryptoRows(data,step,fee).map(r=>r[metric]),itemStyle:{color:colors[index]}}));
  plot.dataset.chartSelection=JSON.stringify({step,metric,values:rows.map(r=>r[metric]),series:series.map(s=>s.data)});plot.dataset.chartColors=JSON.stringify({ink,colors});
  chart.setOption({animation:false,backgroundColor:'transparent',textStyle:{color:ink},aria:{enabled:true,label:{description:t.chartTitle}},legend:{type:'scroll',bottom:0,textStyle:{color:ink}},tooltip:{trigger:'axis',renderMode:'richText',backgroundColor:surface,borderColor:line,textStyle:{color:ink},valueFormatter:(value:unknown)=>typeof value==='number'?format(value,metric):t.unavailable},grid:{left:75,right:20,top:30,bottom:135},xAxis:{type:'category',data:labels,axisLabel:{color:ink,rotate:25,width:110,overflow:'truncate'}},yAxis:{type:'value',axisLabel:{color:ink,formatter:(v:number)=>format(v,metric)},splitLine:{lineStyle:{color:line}}},series},true);
 }};
}
