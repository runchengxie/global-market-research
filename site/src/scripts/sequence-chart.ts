import { init, use } from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
use([LineChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,CanvasRenderer]);
export function createSequenceChart(element:HTMLElement,data:{dates:string[]}) {
 const chart=init(element);
 chart.setOption({tooltip:{trigger:'axis'},legend:{type:'scroll'},grid:{left:60,right:20,top:60,bottom:80},xAxis:{type:'category',data:data.dates},yAxis:{type:'value',scale:true},dataZoom:[{type:'inside'},{type:'slider'}]});
 return chart;
}
