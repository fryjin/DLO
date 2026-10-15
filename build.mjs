import {cp,mkdir,rm} from 'node:fs/promises';
await rm('dist',{recursive:true,force:true});
await mkdir('dist',{recursive:true});
for (const file of ['index.html','styles.css','v8.css','app.js']) await cp(file,`dist/${file}`);
console.log('Built Worker static assets in dist/');
