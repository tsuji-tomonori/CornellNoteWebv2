import tseslint from 'typescript-eslint';
import globals from 'globals';
export default tseslint.config(...tseslint.configs.recommended,{languageOptions:{globals:{...globals.browser,...globals.node}},rules:{'@typescript-eslint/no-explicit-any':'error'}});
