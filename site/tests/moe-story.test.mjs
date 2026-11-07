import assert from 'node:assert/strict';
import {frame,advance,example,STEPS,SCENARIOS} from '../src/lib/moe-story.ts';
assert.equal(STEPS,10);
assert.equal(frame(0).phase,'input');assert.equal(frame(1).phase,'route');assert.equal(frame(2).phase,'dispatch');
for(let i=0;i<5;i++)assert.deepEqual(frame(i+3),{phase:'read',day:i});
assert.equal(frame(8).phase,'mix');assert.equal(frame(9).phase,'output');assert.equal(advance(9),9);assert.equal(advance(0),1);
for(const i of [-1,10,NaN,.5])assert.throws(()=>frame(i));
for(const mode of ['dense','equal','sparse'])for(let s=0;s<SCENARIOS.length;s++){
 const d=example(mode,s);assert.ok(Math.abs(d.weights.reduce((a,b)=>a+b)-1)<1e-12);
 assert.equal(d.selected.length,mode==='sparse'?2:3);
 assert.deepEqual(d.mixture,[0,1].map(j=>d.weights.reduce((sum,w,i)=>sum+w*d.representations[i][j],0)));
 assert.equal(d.score,.7*d.mixture[0]-.4*d.mixture[1]);
 if(mode==='equal')assert.deepEqual(d.weights,[1/3,1/3,1/3]);
 if(mode==='sparse')for(let i=0;i<3;i++)assert.equal(d.weights[i]>0,d.selected.includes(i));
}
assert.ok(example('sparse',2).selected.includes(2));
assert.notDeepEqual(example('dense',0).weights,example('dense',2).weights);
for(const args of [['bogus',0],['dense',-1],['dense',3],['dense',.5]])assert.throws(()=>example(...args));
const {memoryStep}=await import('../src/lib/moe-story.ts');
const m=memoryStep(0,0,0);
assert.equal(m.previous,0);assert.equal(m.cell,m.forget*m.previous+m.write*m.candidate);assert.equal(m.hidden,m.output*Math.tanh(m.cell));
assert.notEqual(memoryStep(0,0,1).previous,0);assert.throws(()=>memoryStep(0,0,5));
