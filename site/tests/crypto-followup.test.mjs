import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateCryptoFollowup} from '../src/lib/crypto-followup.ts';
const data=JSON.parse(readFileSync(new URL('../src/data/crypto-followup.v1.json',import.meta.url),'utf8'));
assert.equal(validateCryptoFollowup(data).comparison.fits_completed,39);
for(const change of [d=>d.private_paths=['/home/private'],d=>d.forward.individual_forecasts=[],d=>d.comparison.fits_completed=38,d=>d.comparison.rows[0].hurdle=.0002,d=>d.provider.historical_availability='verified',d=>d.comparison.rows[0].prediction=.1,d=>d.sources.plan='private',d=>d.comparison.rows[0].net_return='private',d=>d.forward.mse='private',d=>d.comparison.aggregates[0].kind='/private',d=>d.diagnostics.rows[0].count='private']){const d=structuredClone(data);change(d);assert.throws(()=>validateCryptoFollowup(d));}
