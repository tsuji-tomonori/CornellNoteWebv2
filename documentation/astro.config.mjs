import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
const base = process.env.DOCS_BASE || '/design';
export default defineConfig({
 site: 'https://tsuji-tomonori.github.io', base,
 outDir: '../reports/design',
 integrations: [starlight({
  title: 'Cornell / 設計・品質', defaultLocale:'root',
  locales: {root:{label:'日本語',lang:'ja'}},
  customCss:['./src/styles/theme.css'],
  components:{Footer:'./src/components/Footer.astro'},
  sidebar:[
   {label:'品質サマリーへ戻る',link:'../'},
   {label:'設計書の概要',slug:''},
   {label:'API仕様',items:[{autogenerate:{directory:'apis',collapsed:true}}]},
   {label:'データベース・CRUD',items:[{autogenerate:{directory:'database'}}]},
   {label:'AWSインフラ',items:[{autogenerate:{directory:'infrastructure'}}]},
   {label:'単体・結合テスト',items:[{autogenerate:{directory:'tests'}}]},
   {label:'画面',items:[{autogenerate:{directory:'frontend'}}]},
   {label:'要件',items:[{autogenerate:{directory:'requirements'}}],collapsed:true},
  ],
  expressiveCode:{shiki:{langs:[]}},
 })],
});
