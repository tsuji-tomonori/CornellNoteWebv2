import ts from '../frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
const tests=[];
for(const name of fs.readdirSync('frontend/src').filter(n=>/\.test\.tsx?$/.test(n)).sort()){
 const file='frontend/src/'+name;
 const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,name.endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
 function walk(node,parents=[]){
  if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&['test','it','describe'].includes(node.expression.text)){
   const title=node.arguments[0];if(!ts.isStringLiteral(title))throw new Error('Dynamic test title requires extractor support: '+file);
   if(node.expression.text!=='describe')tests.push({file,name:title.text,title:[...parents,title.text].join(' / '),line:ast.getLineAndCharacterOfPosition(node.getStart()).line+1,runner:'Vitest',assertions:[]});
   if(node.expression.text==='describe'){ts.forEachChild(node,n=>walk(n,[...parents,title.text]));return;}
  }
  ts.forEachChild(node,n=>walk(n,parents));
 }
 walk(ast);
}
process.stdout.write(JSON.stringify(tests));
