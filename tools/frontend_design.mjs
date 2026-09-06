import ts from '../frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import path from 'node:path';
const files=fs.readdirSync('frontend/src').filter(x=>/\.tsx?$/.test(x)&&!x.includes('.test.')).sort();
const output=[];
for(const file of files){
 const filename=path.join('frontend/src',file);const code=fs.readFileSync(filename,'utf8');const ast=ts.createSourceFile(filename,code,ts.ScriptTarget.Latest,true,file.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
 if(ast.parseDiagnostics.length)throw new Error('TypeScript parse failure '+filename);
 const functions=[],imports=[],labels=[];
 function visit(node){if(ts.isFunctionDeclaration(node)&&node.name)functions.push({name:node.name.text,parameters:node.parameters.map(p=>p.getText(ast)),returnType:node.type?.getText(ast)||'inferred',line:ast.getLineAndCharacterOfPosition(node.getStart(ast)).line+1});if(ts.isImportDeclaration(node))imports.push(node.moduleSpecifier.text);if(ts.isJsxAttribute(node)&&['aria-label','role','className'].includes(node.name.getText(ast))&&node.initializer&&ts.isStringLiteral(node.initializer))labels.push({attribute:node.name.getText(ast),value:node.initializer.text});ts.forEachChild(node,visit);}
 visit(ast);output.push({path:filename,functions,imports,ui:labels});
}
process.stdout.write(JSON.stringify(output,null,2)+'\n');
