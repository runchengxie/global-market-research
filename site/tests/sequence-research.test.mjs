import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateResearchProjection,selectResearchRows} from '../src/lib/sequence-research.ts';
const data=JSON.parse(readFileSync(new URL('../src/data/sequence-research.v1.json',import.meta.url),'utf8'));
test('published research contains only authorized aggregates with separate experimental denominators',()=>{
 assert.equal(validateResearchProjection(data),data);
 assert.equal(data.primary.rows.length,4);
 assert.equal(data.primary.seeds,5);
 assert.equal(data.target.seeds,3);
 assert.equal(selectResearchRows(data,'primary').length,4);
 assert.throws(()=>selectResearchRows(data,'unknown'));
});
test('private series, extra fields, invalid counts and fabricated probability measures are rejected',()=>{
 for(const mutate of [d=>d.private_path='/private/input',d=>d.primary.rows[0].probabilities=[.4],d=>d.primary.rows[0].auc=1.1,d=>d.primary.rows[0].flat=99,d=>d.architecture.experts=0,d=>d.architecture.experts=4,d=>d.source_revisions.primary='/secret',d=>d.target.rows.push({objective:'regression',auc:.6})]){
  const d=structuredClone(data);mutate(d);assert.throws(()=>validateResearchProjection(d));
 }
});
test('selecting an objective preserves values and never falls back to another study',()=>{
 const frozen=JSON.stringify(data);
 for(const objective of ['classification','regression'])assert.deepEqual(selectResearchRows(data,objective),data.target.rows.filter(r=>r.objective===objective));
 assert.equal(JSON.stringify(data),frozen);
});
