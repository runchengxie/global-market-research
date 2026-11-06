import test from 'node:test';
import assert from 'node:assert/strict';
import { validateSequenceSummary } from '../src/lib/sequence-summary.mjs';
test('public sequence projection rejects private series and requires synthetic label',()=>{
 assert.throws(()=>validateSequenceSummary({schema:'sequence_public_summary.v1',synthetic:false,series:[]}));
 assert.throws(()=>validateSequenceSummary({schema:'sequence_public_summary.v1',synthetic:true,private_path:'/secret',series:[]}));
 assert.doesNotThrow(()=>validateSequenceSummary({schema:'sequence_public_summary.v1',synthetic:true,dates:['D1','D2'],series:[{name:'cash',values:[1,1]}]}));
});
test('synthetic projection has unique IDs and strictly synthetic dates',()=>{
 const base={schema:'sequence_public_summary.v1',synthetic:true,dates:['D1','D2'],series:[{name:'cash',values:[1,1]}]};
 assert.throws(()=>validateSequenceSummary({...base,dates:['D1','/private/input']}));
 assert.throws(()=>validateSequenceSummary({...base,dates:['D1','</script>']}));
 assert.throws(()=>validateSequenceSummary({...base,series:[...base.series,...base.series]}));
});
