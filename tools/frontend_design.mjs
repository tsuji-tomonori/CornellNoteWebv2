import ts from '../frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import path from 'node:path';
const files=fs.readdirSync('frontend/src').filter(x=>/\.tsx?$/.test(x)&&!x.includes('.test.')).sort();
const output=[];
for(const file of files){
 const filename=path.join('frontend/src',file);const code=fs.readFileSync(filename,'utf8');const ast=ts.createSourceFile(filename,code,ts.ScriptTarget.Latest,true,file.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
 if(ast.parseDiagnostics.length)throw new Error('TypeScript parse failure '+filename);
 const functions=[],imports=[],labels=[],types=[];
 function visit(node){if(ts.isTypeAliasDeclaration(node)||ts.isInterfaceDeclaration(node))types.push(node.getText(ast));if(ts.isFunctionDeclaration(node)&&node.name)functions.push({name:node.name.text,parameters:node.parameters.map(p=>p.getText(ast)),returnType:node.type?.getText(ast)||'inferred',line:ast.getLineAndCharacterOfPosition(node.getStart(ast)).line+1});if(ts.isImportDeclaration(node))imports.push(node.moduleSpecifier.text);if(ts.isJsxAttribute(node)&&['aria-label','role','className'].includes(node.name.getText(ast))&&node.initializer&&ts.isStringLiteral(node.initializer))labels.push({attribute:node.name.getText(ast),value:node.initializer.text});ts.forEachChild(node,visit);}
 visit(ast);output.push({path:filename,functions,imports,types,ui:labels});
}
const cases=[];
const testPath='frontend/e2e/notes.spec.ts';
const testAst=ts.createSourceFile(testPath,fs.readFileSync(testPath,'utf8'),ts.ScriptTarget.Latest,true);
if(testAst.parseDiagnostics.length)throw new Error('Invalid Playwright source');
function literal(node){if(!node||!ts.isStringLiteral(node))throw new Error('Dynamic test metadata needs extractor support');return node.text;}
for(const statement of testAst.statements){
 if(!ts.isExpressionStatement(statement)||!ts.isCallExpression(statement.expression))continue;
 const call=statement.expression;if(call.expression.getText(testAst)!=='test')continue;
 const title=literal(call.arguments[0]),steps=[];
 function walk(node){
  if(ts.isCallExpression(node)&&node.expression.getText(testAst)==='step')steps.push({kind:literal(node.arguments[2]),text:literal(node.arguments[3])});
  ts.forEachChild(node,walk);
 }
 walk(call.arguments[1]);
 if(!['Given','When','Then'].every(kind=>steps.some(step=>step.kind===kind)))throw new Error('Missing GWT '+title);
 cases.push({title,steps});
}
process.stdout.write(JSON.stringify({files:output,cases},null,2)+'\n');
