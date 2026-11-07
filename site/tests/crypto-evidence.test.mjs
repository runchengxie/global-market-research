import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateCryptoEvidence,selectCryptoRows} from '../src/lib/crypto-evidence.ts';
const facts=JSON.parse(readFileSync(new URL('../src/data/crypto-evidence.v1.json',import.meta.url),'utf8'));
assert.equal(validateCryptoEvidence(facts).experiment.fit_count,24);
assert.equal(selectCryptoRows(facts,4,10).length,8);
for(const change of [d=>d.raw_prices=[1],d=>d.rows[0].predictions=[.1],d=>d.experiment.fit_count=23,d=>d.sources.fit_revision='/home/private',d=>d.observation.scored_forecasts=d.observation.committed_forecasts+1]){const d=structuredClone(facts);change(d);assert.throws(()=>validateCryptoEvidence(d));}
const clone=structuredClone(facts);clone.rows[0].skill=null;assert.equal(validateCryptoEvidence(clone).rows[0].skill,null);
const equalTime=structuredClone(facts);const start=equalTime.experiment.test_windows[0][0];equalTime.experiment.test_windows[0]=[start.replace('Z','+00:00'),start];assert.throws(()=>validateCryptoEvidence(equalTime));
const badStatus=structuredClone(facts);badStatus.operations.health_status='unknown_ready';assert.throws(()=>validateCryptoEvidence(badStatus));
