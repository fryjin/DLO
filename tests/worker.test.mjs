import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHmac,randomBytes,webcrypto} from 'node:crypto';
import worker,{checkDocument} from '../src/worker.js';
if (!globalThis.crypto) globalThis.crypto=webcrypto;

const pepper=randomBytes(32).toString('hex');
const secret=randomBytes(32).toString('base64url');
const secrets={admin01:secret,admin02:randomBytes(32).toString('base64url'),admin03:randomBytes(32).toString('base64url')};
const hashes=Object.fromEntries(Object.entries(secrets).map(([name,key])=>[name,createHmac('sha256',pepper).update(name+':'+key).digest('hex')]));
function createDB(){
 const users=new Map(Object.keys(secrets).map((username,i)=>[username,{id:`fixed-account-${i+1}`,username,secret_hash:hashes[username],enabled:1}]));
 const sessions=new Map(), limits=new Map();
 let doc={data_json:null,version:0,updated_at:null,updated_by:null};
 return {prepare(sql){let binds=[];return {
   bind(...a){binds=a;return this;},
   async first(){
     if(sql.includes('FROM sessions JOIN users')){const row=sessions.get(binds[0]);if(!row||row.expires_at<=binds[1])return null;return [...users.values()].find(x=>x.id===row.user_id)||null;}
     if(sql.includes('SELECT fails,window_start'))return limits.get(binds[0])||null;
     if(sql.includes('SELECT id,username,secret_hash'))return users.get(binds[0])||null;
     if(sql.includes('SELECT data_json,version'))return doc;
     if(sql.includes('UPDATE shared_document')){doc={data_json:binds[0],version:doc.version+1,updated_at:binds[1],updated_by:binds[2]};return doc;}
     return null;
   },
   async run(){
     if(sql.startsWith('INSERT INTO sessions'))sessions.set(binds[0],{user_id:binds[1],expires_at:binds[2]});
     else if(sql.startsWith('DELETE FROM sessions'))sessions.delete(binds[0]);
     else if(sql.startsWith('DELETE FROM login_limits'))limits.delete(binds[0]);
     else if(sql.startsWith('INSERT INTO login_limits')){let record=limits.get(binds[0]);if(!record||binds[1]-record.window_start>=15*60_000)record={fails:0,window_start:binds[1]};record.fails++;limits.set(binds[0],record);}
     return {success:true};
   }
 };}};
}
const db=createDB();
const env={DB:db,KEY_PEPPER:pepper,ASSETS:{fetch:()=>new Response('ok')}};
const URL='https://pricing.example.com';
function request(path,method='GET',body=null,cookie='') {return new Request(URL+path,{method,headers:{...(method==='POST'?{'content-type':'application/json','origin':URL}:{}),...(cookie?{'cookie':cookie}:{})},...(body===null?{}:{body:JSON.stringify(body)})});}
const emptyState={version:4,currentProjectId:'p1',projects:[{id:'p1',name:'项目',currentPackageId:'k1',costItems:[],packages:[{id:'k1',name:'套餐',products:[],discounts:[{id:'a',zhe:'6'}],fees:[]}]}]};

test('state shape guard',()=>{assert.ok(checkDocument(emptyState));assert.equal(checkDocument({version:4,projects:[]}),false);});
test('rejects unauthenticated, invalid login, CSRF and grants identical access to shared state',async()=>{
 assert.equal((await worker.fetch(request('/api/state'),env)).status,401);
 const bad=await worker.fetch(request('/api/login','POST',{username:'admin01',secret:'X'.repeat(32)}),env);
 assert.equal(bad.status,401);
 const evil=new Request(URL+'/api/login',{method:'POST',headers:{origin:'https://evil.example','content-type':'application/json'},body:JSON.stringify({username:'admin01',secret})});
 assert.equal((await worker.fetch(evil,env)).status,403);
 const login=await worker.fetch(request('/api/login','POST',{username:'admin01',secret}),env);
 assert.equal(login.status,200);
 const cookie=login.headers.get('set-cookie');
 assert.match(cookie,/HttpOnly/);assert.match(cookie,/SameSite=Lax/);assert.match(cookie,/Secure/);
 const header=cookie.split(';')[0];
 assert.equal((await worker.fetch(request('/api/me','GET',null,header),env)).status,200);
 assert.equal((await worker.fetch(request('/api/state','GET',null,header),env)).status,200);
 assert.equal((await worker.fetch(request('/api/state','POST',{state:emptyState},header),env)).status,200);
 const saved=await (await worker.fetch(request('/api/state','GET',null,header),env)).json();
 assert.equal(saved.revision,1);assert.deepEqual(saved.state,emptyState);
 assert.equal((await worker.fetch(request('/api/state','POST',{state:{broken:true}},header),env)).status,400);
 const update=await (await worker.fetch(request('/api/state','POST',{state:{...emptyState,currentProjectId:'p1'}},header),env)).json();
 assert.equal(update.revision,2);
 assert.equal((await worker.fetch(request('/api/logout','POST',{},header),env)).status,200);
 assert.equal((await worker.fetch(request('/api/state','GET',null,header),env)).status,401);
});

test('friendly account names reuse original three credentials and shared document',async()=>{
 const table=[['炮台','admin01'],['芋头','admin02'],['EE','admin03']];
 for(const [name,canonical] of table){
   const login=await worker.fetch(request('/api/login','POST',{username:name,secret:secrets[canonical]}),env);
   assert.equal(login.status,200,`failed alias ${name}`);
   const body=await login.json();
   assert.deepEqual(body.user,{username:canonical,displayName:name});
   const cookie=login.headers.get('set-cookie').split(';')[0];
   const me=await (await worker.fetch(request('/api/me','GET',null,cookie),env)).json();
   assert.deepEqual(me.user,{username:canonical,displayName:name});
   const data=await worker.fetch(request('/api/state','GET',null,cookie),env);
   assert.equal(data.status,200);
 }
 const legacy=await worker.fetch(request('/api/login','POST',{username:'admin02',secret:secrets.admin02}),env);
 assert.equal(legacy.status,200,'existing credentials must remain valid');
 assert.equal((await legacy.json()).user.displayName,'芋头');
 const wrong=await worker.fetch(request('/api/login','POST',{username:'EE',secret:secrets.admin01}),env);
 assert.equal(wrong.status,401,'aliases must not grant other users credentials');
});
