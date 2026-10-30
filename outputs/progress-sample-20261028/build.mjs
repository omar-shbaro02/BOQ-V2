import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const dir = fileURLToPath(new URL('.', import.meta.url));
const source = '../../.data/governed-generation-result.xlsx';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const tasks = wb.worksheets.getItem('Tasks').getUsedRange().values.slice(1).filter(r => r[0] != null);
const coverage = wb.worksheets.getItem('BOQ Coverage').getUsedRange().values.slice(1);
const serial = s => Math.round((Date.parse(String(s).slice(0,10)) - Date.UTC(1899,11,30))/86400000);
const cutoff = serial('2027-06-30');
const p = wb.worksheets.add('Progress Report');
const c = wb.worksheets.add('Schedule Comparison');
const headers = ['Subdivision','Task ID','Task Name','Proposed Duration','Planned Start','Planned Finish','Work Complete %','Reporting Date','Remarks','Evidence Reference','Responsible Party','Planning Basis'];
p.getRange('A1:L1').merge(); p.getRange('A1').values = [['SAMPLE ONLY — fictional progress at 30 June 2027; replace yellow inputs with site observations.']];
p.getRange('A2:L2').merge(); p.getRange('A2').values = [['Baseline unchanged. Subdivisions group source BOQ section numbers; exact row-to-task mapping remains in BOQ Coverage.']];
p.getRange('A4:L4').values = [headers];
const sample = tasks.map((t,i) => {
 const start = serial(t[3]), end = serial(t[4]);
 const plan = cutoff < start ? 0 : cutoff >= end ? 100 : (cutoff-start+1)/(end-start+1)*100;
 const pct = plan === 0 ? 0 : Math.max(0,Math.min(100, Math.round(plan + [-25,0,15,-10,0][i%5])));
 const refs = coverage.filter(r => String(r[4]??'').split(',').map(x=>Number(x.trim())).includes(Number(t[0]))).map(r=>String(r[0]));
 const sections = [...new Set(refs.map(r=>r.match(/:(\d+)/)?.[1]).filter(Boolean))];
 return [sections.length ? sections.map(x=>`BOQ section ${x}`).join('; ') : 'EXECUTION SUPPORT — no mapped BOQ row',t[0],t[1],t[2],t[3],t[4],pct,'2027-06-30',`FICTIONAL SAMPLE: ${plan===0?'not yet started':pct<plan-5?'behind planned completion':pct>plan+5?'ahead of planned completion':'tracking plan'}. Replace with observed update.`,null,'SAMPLE — replace with responsible person','SOURCE PROPOSED SCHEDULE; NOT AN AUTHORIZED BASELINE'];
});
p.getRange(`A5:L${sample.length+4}`).values = sample;
p.getRange(`G5:K${sample.length+4}`).format.fill = '#FFF2CC';
p.getRange(`G5:G${sample.length+4}`).setNumberFormat('0.0"%"');
p.getRange(`G5:G${sample.length+4}`).dataValidation = {rule:{type:'decimal',operator:'between',formula1:0,formula2:100}};
p.freezePanes.freezeRows(4);
c.getRange('A1:L1').merge(); c.getRange('A1').values = [['SAMPLE PROGRESS • comparison against the original proposed schedule']];
c.getRange('A2').values = [['Reporting cut-off']]; c.getRange('B2').values = [[cutoff]]; c.getRange('B2').setNumberFormat('dd mmm yyyy'); c.getRange('B2').format.fill='#FFF2CC';
c.getRange('A3:L3').merge(); c.getRange('A3').values = [['Calendar-day approximation; status tolerance ±5 percentage points. Positive days = ahead; negative = behind. Not a critical-path deadline forecast.']];
c.getRange('A4:L4').merge(); c.getRange('A4').values = [['Source: .data/governed-generation-result.xlsx. Fictional reporting date chosen mid-schedule to demonstrate completed, active and future activities.']];
c.getRange('A6:B10').values = [['Task status','Count'],['EARLY',null],['ON TIME',null],['LATE',null],['NOT REPORTED',null]];
for(let r=7;r<=10;r++) c.getRange(`B${r}`).formulas=[[`=COUNTIFS(K14:K${tasks.length+13},A${r})`]];
c.getRange('D6:L6').merge(); c.getRange('D6').values=[['Edit yellow cells on Progress Report; use the same cut-off here and in the app.']];
c.getRange('D7:L7').merge(); c.getRange('D7').values=[['Upload this entire workbook on /progress → Preview workbook. Tasks and Progress Report use the app’s required headers.']];
c.getRange('D8:L8').merge(); c.getRange('D8').values=[['No project-wide completion average is inferred: approved weights/quantities are required for that calculation.']];
c.getRange('A13:L13').values=[['Task ID','Task / activity','BOQ subdivision','Planned start','Planned finish','Duration (days)','Planned %','Reported %','Variance (pp)','Approx. days +/−','Status','Reporting date']];
for(let i=0;i<tasks.length;i++) {
 const r=i+14,q=i+5,t=tasks[i];
 c.getRange(`A${r}:F${r}`).values=[[t[0],t[1],sample[i][0],serial(t[3]),serial(t[4]),Number(String(t[2]).match(/\d+/)[0])]];
 c.getRange(`G${r}:L${r}`).formulas=[[
 `=IF($B$2<D${r},0,IF($B$2>=E${r},100,MIN(100,($B$2-D${r}+1)/(E${r}-D${r}+1)*100)))`,
 `=IF(ISNUMBER('Progress Report'!G${q}),'Progress Report'!G${q},"")`,
 `=IF(ISNUMBER(H${r}),H${r}-G${r},"")`,
 `=IF(ISNUMBER(I${r}),ROUND(I${r}/100*F${r},1),"")`,
 `=IF(ISNUMBER(H${r}),IF(I${r}>5,"EARLY",IF(I${r}<-5,"LATE","ON TIME")),"NOT REPORTED")`,
 `='Progress Report'!H${q}`]];
}
c.getRange(`D14:E${tasks.length+13}`).setNumberFormat('dd mmm yyyy');
c.getRange(`G14:H${tasks.length+13}`).setNumberFormat('0.0"%"');
c.getRange(`I14:J${tasks.length+13}`).setNumberFormat('+0.0;-0.0;0.0');
c.freezePanes.freezeRows(13);
for(const [s,last,header] of [[p,sample.length+4,4],[c,tasks.length+13,13]]) {
 s.showGridLines=false;
 s.getRange(`A1:L${last}`).format.font={name:'Aptos',size:11,color:'#282329'};
 s.getRange(`A${header}:L${header}`).format.fill='#781633';
 s.getRange(`A${header}:L${header}`).format.font={bold:true,color:'#FFFFFF'};
 s.getRange(`A${header}:L${header}`).format.wrapText=true;
 s.getRange(`A${header}:L${header}`).format.rowHeight=38;
 s.getRange(`A${header+1}:L${last}`).format.rowHeight=48;
 s.getRange(`A${header+1}:L${last}`).format.wrapText=true;
 s.getRange(`A1:L${last}`).format.columnWidth=17;
}
p.getRange('A:A').format.columnWidth=32; p.getRange('C:C').format.columnWidth=62;
p.getRange('I:I').format.columnWidth=62; p.getRange('K:L').format.columnWidth=36;
c.getRange('B:B').format.columnWidth=62; c.getRange('C:C').format.columnWidth=32;
c.getRange('K:K').format.columnWidth=21;
for(const status of ['LATE','EARLY','ON TIME','NOT REPORTED']) {
 c.getRange(`K14:K${tasks.length+13}`).conditionalFormats.add('containsText',{text:status,format:{fill:status==='LATE'?'#FCE0E4':status==='EARLY'?'#DAECE8':status==='ON TIME'?'#E9F0FA':'#FFF2CC'}});
}
for(const [name,widths,head] of [['BOQ Coverage',[26,90,16,14,25,30,16],1],['QA Review',[20,16,18,95,75,95,26],2]]) {
 const sheet=wb.worksheets.getItem(name);
 for(let i=0;i<widths.length;i++) sheet.getRange(`${String.fromCharCode(65+i)}:${String.fromCharCode(65+i)}`).format.columnWidth=widths[i];
 sheet.getRange(`A${head}:G${head}`).format.wrapText=true;
 sheet.getRange(`A${head}:G${head}`).format.rowHeight=34;
}
// Verify editable inputs distinguish a true zero from absent reporting, then restore.
const original=p.getRange('G5').values;
p.getRange('G5').values=[[0]]; wb.recalculate();
if(c.getRange('H14').values[0][0]!==0 || c.getRange('K14').values[0][0]!=='LATE') throw Error('Zero reporting check');
p.getRange('G5').values=[[null]]; wb.recalculate();
if(c.getRange('K14').values[0][0]!=='NOT REPORTED') throw Error('Missing reporting check');
p.getRange('G5').values=original;
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Schedule Comparison!A6:B10',include:'values,formulas',tableMaxRows:5,tableMaxCols:2})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20}})).ndjson);
for(const [sheet,range,name] of [['Schedule Comparison','A1:L18','comparison'],['Progress Report','A1:L9','progress'],['Tasks','A1:F6','tasks'],['BOQ Coverage','A1:G6','coverage'],['QA Review','A1:G6','qa']]) {
 const img=await wb.render({sheetName:sheet,range,scale:1.3,format:'png'});
 await fs.writeFile(`${dir}/${name}.png`,new Uint8Array(await img.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/sample-progress-comparison.xlsx`);
console.log('Saved sample-progress-comparison.xlsx');
