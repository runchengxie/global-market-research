// This first projection admits synthetic fixtures only; real publication is separate.
export function validateSequenceSummary(data) {
  if (!data || data.schema !== 'sequence_public_summary.v1' || data.synthetic !== true ||
      Object.keys(data).some(k => !['schema','synthetic','dates','series'].includes(k)) ||
      !Array.isArray(data.dates) || data.dates.some((d,i)=>d!==`D${i+1}`) || data.dates.length < 2 || !Array.isArray(data.series) || !data.series.length || new Set(data.series.map(s=>s.name)).size !== data.series.length ||
      data.series.some(s => Object.keys(s).some(k=>!['name','values'].includes(k)) ||
        !['cash','holding','dense','sparse'].includes(s.name) || !Array.isArray(s.values) ||
        s.values.length !== data.dates.length || s.values.some(v=>!Number.isFinite(v)||v<=0))) {
    throw new Error('Invalid synthetic sequence projection');
  }
  return data;
}
