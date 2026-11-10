import fs from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/__anchor__.cjs');
const { Workbook, SpreadsheetFile, FileBlob } = require('@oai/artifact-tool');
const outputDir = 'C:/Users/alexc/Documents/GitHub/PING Project/outputs/01a1c062-77d4-7853-b6a0-eefbec54f94f';
const outputPath = `${outputDir}/rover_mass_budget.xlsx`;

const wb = Workbook.create();
const ws = wb.worksheets.add('Mass budget');
ws.showGridLines = false;
ws.tabColor = '#203B5E';

const items = [
  ['Drive', '30:1 37D motor with encoder', 4, 200, 1, null, 'Published mass: Pololu #4752'],
  ['Drive', '50:1 37D motor alternative', 4, 205, 0, null, 'Published mass: Pololu #4753; excluded'],
  ['Drive', 'Hollow 120 mm wheel', 4, 100, 1, null, 'Estimate used in motor sizing'],
  ['Drive', '6 mm wheel hub or adapter', 4, 25, 1, null, 'Planning estimate'],
  ['Structure', 'Printed chassis and body', 1, 450, 1, null, 'Planning estimate; PETG or PLA'],
  ['Structure', 'Suspension corner assembly', 4, 80, 1, null, 'Planning estimate'],
  ['Structure', 'Fasteners and bearings', 1, 180, 1, null, 'Planning estimate'],
  ['Power', 'Battery cells and pack', 1, 500, 1, null, 'Planning estimate; capacity undecided'],
  ['Power', 'Battery management system', 1, 60, 1, null, 'Planning estimate'],
  ['Power', 'Power wiring and connectors', 1, 120, 1, null, 'Planning estimate'],
  ['Electronics', 'Raspberry Pi onboard computer', 1, 60, 1, null, 'Planning estimate; selected for this case'],
  ['Electronics', 'ESP32 computer alternative', 1, 20, 0, null, 'Alternative to Pi; excluded'],
  ['Electronics', 'Dual-channel motor driver board', 2, 50, 1, null, 'Planning estimate; two boards for four motors'],
  ['Electronics', 'Custom control PCB and electronics', 1, 80, 1, null, 'Planning estimate'],
  ['Electronics', 'Radio module and antenna', 1, 50, 1, null, 'Planning estimate'],
  ['Sensors / camera', 'IMU', 1, 15, 1, null, 'Planning estimate from project scope'],
  ['Sensors / camera', 'Physical distance sensor', 1, 40, 1, null, 'Planning estimate; software sensor is simulated'],
  ['Sensors / camera', 'Pi HQ camera and lens', 1, 75, 1, null, 'Planning estimate; exact lens undecided'],
  ['Sensors / camera', 'Gimbal servos', 2, 60, 1, null, 'Planning estimate; two axes'],
  ['Sensors / camera', 'Gimbal mount and brackets', 1, 100, 1, null, 'Planning estimate'],
  ['Other', 'Additional mounts and enclosure', 1, 150, 1, null, 'Planning estimate'],
];

ws.getRange('A2').values = [['PING rover mass budget']];
ws.getRange('A3:A8').values = [
  ['Mass target, low (kg)'],
  ['Mass target, high (kg)'],
  ['Included parts (kg)'],
  ['Assembly allowance'],
  ['Planning mass (kg)'],
  ['Headroom to high target (kg)'],
];
ws.getRange('B3').values = [[3]];
ws.getRange('B4').values = [[4]];
ws.getRange('B5').formulas = [['=F33/1000']];
ws.getRange('B6').values = [[0.15]];
ws.getRange('B7').formulas = [['=B5*(1+B6)']];
ws.getRange('B8').formulas = [['=B4-B7']];
ws.getRange('D2').values = [['Mass by subsystem (kg)']];
ws.getRange('D3:D8').values = [['Drive'], ['Structure'], ['Power'], ['Electronics'], ['Sensors / camera'], ['Other']];
ws.getRange('E3').formulas = [['=SUMIFS($F$12:$F$32,$A$12:$A$32,D3)/1000']];
ws.getRange('E3:E8').fillDown();
ws.getRange('A10').values = [['Edit yellow cells as parts are selected or weighed. Include only one computer and one motor choice.']];
ws.getRange('A11:G11').values = [['Subsystem', 'Component', 'Quantity', 'Unit mass (g)', 'Include (1/0)', 'Included mass (g)', 'Basis']];
ws.getRange('A12:G32').values = items;
ws.getRange('F12').formulas = [['=C12*D12*E12']];
ws.getRange('F12:F32').fillDown();
ws.getRange('A33').values = [['Included parts total (g)']];
ws.getRange('F33').formulas = [['=SUM(F12:F32)']];
ws.getRange('A36').values = [['Sources and scope']];
ws.getRange('A37').values = [['30:1 motor mass']];
ws.getRange('B37').values = [['Pololu #4752: 200 g per motor']];
ws.getRange('G37').values = [['https://www.pololu.com/product/4752/specs']];
ws.getRange('A38').values = [['50:1 motor mass']];
ws.getRange('B38').values = [['Pololu #4753: 205 g per motor']];
ws.getRange('G38').values = [['https://www.pololu.com/product/4753/specs']];
ws.getRange('A39').values = [['Project scope']];
ws.getRange('B39').values = [['Proposal: 4WD, suspension, sensors, BMS, PCB and hardware.']];
ws.getRange('A40').values = [['Software scope']];
ws.getRange('B40').values = [['Rover description: camera, gimbal and rangefinder concepts.']];
ws.getRange('A41').values = [['Estimate basis']];
ws.getRange('B41').values = [['Other masses are estimates; 15% allowance is separate.']];

const navy = '#203B5E';
const blue = '#EAF1F8';
const amber = '#FFF1C9';
const gray = '#64748B';
const lightRule = '#D6DEE7';
ws.getRange('A2:G41').format.font = { name: 'Arial', size: 10, color: '#202B38' };
ws.getRange('A2:G41').format.verticalAlignment = 'center';
ws.getRange('A2:G2').format.borders = { bottom: { style: 'thin', color: lightRule } };
ws.getRange('A2').format.font = { name: 'Arial', size: 15, bold: true, color: navy };
ws.getRange('D2').format.font = { name: 'Arial', size: 11, bold: true, color: navy };
ws.getRange('A36').format.font = { name: 'Arial', size: 11, bold: true, color: navy };
ws.getRange('A11:G11').format = { fill: navy, font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, verticalAlignment: 'center' };
ws.getRange('A11:G11').format.rowHeight = 27;
ws.getRange('A12:G32').format.rowHeight = 23;
ws.getRange('A33:G33').format = { fill: blue, font: { name: 'Arial', size: 10, bold: true, color: navy }, verticalAlignment: 'center' };
ws.getRange('A33:G33').format.rowHeight = 25;
ws.getRange('C12:E32').format.fill = amber;
ws.getRange('B3:B4').format.fill = amber;
ws.getRange('B6').format.fill = amber;
ws.getRange('B5').format.fill = blue;
ws.getRange('B7:B8').format.fill = blue;
ws.getRange('F12:F32').format.fill = blue;
ws.getRange('G12:G32').format.font = { name: 'Arial', size: 10, color: gray };
ws.getRange('A10').format.font = { name: 'Arial', size: 10, italic: true, color: gray };
ws.getRange('A10:G10').format.rowHeight = 23;
ws.getRange('A36:G36').format.borders = { bottom: { style: 'thin', color: lightRule } };
ws.getRange('A37:G41').format.rowHeight = 24;
ws.getRange('B37:B41').format.font = { name: 'Arial', size: 10, color: gray };
ws.getRange('G37:G41').format.font = { name: 'Arial', size: 10, color: gray };
ws.getRange('B3:B5').setNumberFormat('0.00');
ws.getRange('B6').setNumberFormat('0%');
ws.getRange('B7:B8').setNumberFormat('0.00');
ws.getRange('E3:E8').setNumberFormat('0.00');
ws.getRange('C12:C32').setNumberFormat('0');
ws.getRange('D12:D32').setNumberFormat('0');
ws.getRange('E12:E32').setNumberFormat('0');
ws.getRange('F12:F33').setNumberFormat('0');
ws.getRange('C11:F33').format.horizontalAlignment = 'right';
ws.getRange('C11:F11').format.horizontalAlignment = 'center';
ws.getRange('A2:A41').format.columnWidth = 25;
ws.getRange('B2:B41').format.columnWidth = 38;
ws.getRange('C2:C41').format.columnWidth = 11;
ws.getRange('D2:D41').format.columnWidth = 18;
ws.getRange('E2:E41').format.columnWidth = 18;
ws.getRange('F2:F41').format.columnWidth = 20;
ws.getRange('G2:G41').format.columnWidth = 48;
ws.getRange('B8').conditionalFormats.add('cellIs', { operator: 'lessThan', formula: 0, format: { fill: '#FCE8E6', font: { bold: true, color: '#9A2525' } } });

wb.recalculate();
const top = await wb.inspect({ kind: 'table', range: 'Mass budget!A2:G8', include: 'values,formulas', tableMaxRows: 8, tableMaxCols: 7 });
const totals = await wb.inspect({ kind: 'table', range: 'Mass budget!A31:G33', include: 'values,formulas', tableMaxRows: 3, tableMaxCols: 7 });
const errors = await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'formula errors' });
console.log('TOP', top.ndjson);
console.log('TOTALS', totals.ndjson);
console.log('ERRORS', errors.ndjson);
const preview = await wb.render({ sheetName: 'Mass budget', range: 'A1:G41', scale: 1.5, format: 'png' });
await fs.writeFile(`${outputDir}/rover_mass_budget_preview.png`, new Uint8Array(await preview.arrayBuffer()));
await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const checkSheet = reopened.worksheets.getItem('Mass budget');
reopened.recalculate();
const near = (actual, expected) => Math.abs(actual - expected) < 1e-8;
if (!near(checkSheet.getRange('B5').values[0][0], 3.72) || !near(checkSheet.getRange('B7').values[0][0], 4.278)) {
  throw new Error('Saved workbook totals failed the round-trip check');
}
checkSheet.getRange('D14').values = [[150]];
reopened.recalculate();
if (!near(checkSheet.getRange('B5').values[0][0], 3.92)) {
  throw new Error('Wheel mass edit did not update the saved workbook');
}
console.log('CHECK', 'Round-trip and editable wheel mass passed');
console.log('SAVED', outputPath);
