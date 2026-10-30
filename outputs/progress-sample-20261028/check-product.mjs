import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load('../../.test-tmp/progress-template-product.xlsx'));
const expected=JSON.parse(await fs.readFile('../../.test-tmp/progress-template-expected.json','utf8'));
wb.recalculate();
const comparison=wb.worksheets.getItem('Schedule Comparison');
for(let i=0;i<expected.rows.length;i++) {
 const actual=comparison.getRange(`G${i+5}:K${i+5}`).values[0], e=expected.rows[i];
 if(Math.abs(actual[0]-e.planned_percent)>0.051 || actual[1]!==e.reported_percent || actual[3]!==e.schedule_variance_days || actual[4]!==e.status) throw Error(`Comparison mismatch row ${i+5}: ${JSON.stringify(actual)}`);
}
const progress=wb.worksheets.getItem('Progress Report');
progress.getRange('G5').values=[[null]];wb.recalculate();
if(comparison.getRange('K5').values[0][0]!=='NOT REPORTED') throw Error('Missing-input behavior');
progress.getRange('G5').values=[[0]];wb.recalculate();
if(comparison.getRange('H5').values[0][0]!==0) throw Error('Zero-input behavior');
console.log(`Validated ${expected.rows.length} calculated rows against application preview; blank/zero edits recalculate.`);
for(const [sheet,range,file] of [['Progress Report','A1:L8','product-progress'],['Schedule Comparison','A1:K8','product-comparison']]) {
 const image=await wb.render({sheetName:sheet,range,scale:1.2,format:'png'});
 await fs.writeFile(`../../.test-tmp/${file}.png`,new Uint8Array(await image.arrayBuffer()));
}
