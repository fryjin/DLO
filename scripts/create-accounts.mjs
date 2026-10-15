// Generates THREE random login keys and a SQL seed file on this machine.
// DO NOT commit generated files. This script is rerunnable and rotates all three logins.
import {randomBytes,createHmac} from 'node:crypto';
import {mkdir,writeFile} from 'node:fs/promises';
const usernames=['admin01','admin02','admin03'];
const pepper=process.env.KEY_PEPPER || randomBytes(32).toString('hex');
if (pepper.length<32) throw new Error('KEY_PEPPER must have at least 32 characters');
const now=Date.now();
const accounts=usernames.map((username,index)=>{
 const secret=randomBytes(32).toString('base64url');
 const hash=createHmac('sha256',pepper).update(username+':'+secret).digest('hex');
 return {username,secret,hash,id:`fixed-account-${index+1}`};
});
await mkdir('.private',{recursive:true});
const sql=accounts.map(a=>`INSERT INTO users(id,username,secret_hash,enabled,created_at) VALUES('${a.id}','${a.username}','${a.hash}',1,${now}) ON CONFLICT(username) DO UPDATE SET secret_hash=excluded.secret_hash,enabled=1;`).join('\n');
await writeFile('.private/seed-users.sql',sql+'\n',{mode:0o600});
await writeFile('.private/login-credentials.txt',`DO NOT UPLOAD TO GITHUB\n\nKEY_PEPPER (Worker secret): ${pepper}\n\n`+accounts.map(a=>`${a.username}: ${a.secret}`).join('\n')+'\n',{mode:0o600});
console.log('Generated .private/seed-users.sql and .private/login-credentials.txt');
console.log('IMPORTANT: protect the private folder; deploy KEY_PEPPER as a Worker secret.');
