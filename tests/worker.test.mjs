import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHmac,randomBytes,webcrypto} from 'node:crypto';
import worker,{checkDocument} from '../src/worker.js';
if(!globalThis.crypto)globalThis.crypto=webcrypto;

const ORIGIN='https://dopamine.example.com';
const LABELS={admin01:'炮台',admin02:'芋头',admin03:'EE'};
const pepper=randomBytes(32).toString('hex');
const secrets=Object.fromEntries(Object.keys(LABELS).map(u=>[u,randomBytes(32).toString('base64url')]));
function fixture(name='测试项目',cost='0.1'){
 return {version:4,currentProjectId:'p1',projects:[{
  id:'p1',name,currentPackageId:'pk1',costItems:[{id:'c1',type:'product',name:'测试',spec:'',cost,listPrice:'0.3',active:true,components:[]}],
  packages:[{id:'pk1',name:'套餐',products:[],discounts:[{id:'d1',zhe:'6'}],fees:[]}]
 }]};
}
function environment({legacy=fixture('旧共享资料')}={}){
 const users=new Map(Object.keys(LABELS).map((username,i)=>[username,{
  id:`fixed-account-${i+1}`,username,enabled:1,
  secret_hash:createHmac('sha256',pepper).update(username+':'+secrets[username]).digest('hex')
 }]));
 const docs=new Map([...users.values()].map(u=>[u.id,{
  data_json:legacy?JSON.stringify(legacy):null,version:legacy?5:0,
  updated_at:null,updated_by:null
 }]));
 const sessions=new Map(),limits=new Map();
 const DB={prepare(sql){let binds=[];return{
  bind(...v){binds=v;return this;},
  async first(){
   if(sql.includes('FROM sessions JOIN users')){
     const t=sessions.get(binds[0]);return t&&t.expires_at>binds[1]?[...users.values()].find(u=>u.id===t.user_id)||null:null;
   }
   if(sql.includes('SELECT fails,window_start'))return limits.get(binds[0])||null;
   if(sql.includes('SELECT id,username,secret_hash'))return users.get(binds[0])||null;
   if(sql.includes('FROM account_documents AS d JOIN users AS u')){
    const u=users.get(binds[0]);return u?docs.get(u.id)||null:null;
   }
   if(sql.includes('SET data_json=?')){
    const row=docs.get(binds[3]);if(!row)return null;
    row.data_json=binds[0];row.version++;row.updated_at=binds[1];row.updated_by=binds[2];
    return {version:row.version,updated_at:row.updated_at,updated_by:row.updated_by};
   }
   if(sql.includes('SET data_json=(SELECT src.data_json')){
    const source=users.get(binds[0]),target=docs.get(binds[3]);const src=source?docs.get(source.id):null;
    if(!source?.enabled || !src?.data_json || !target)return null;
    target.data_json=src.data_json;target.version++;target.updated_at=binds[1];target.updated_by=binds[2];
    return {version:target.version,updated_at:target.updated_at,updated_by:target.updated_by};
   }
   return null;
  },
  async run(){
   if(sql.startsWith('INSERT INTO sessions'))sessions.set(binds[0],{user_id:binds[1],expires_at:binds[2]});
   if(sql.startsWith('DELETE FROM sessions'))sessions.delete(binds[0]);
   if(sql.startsWith('DELETE FROM login_limits'))limits.delete(binds[0]);
   if(sql.startsWith('INSERT INTO login_limits')){
    let r=limits.get(binds[0]);if(!r||binds[1]-r.window_start>=900000)r={fails:0,window_start:binds[1]};r.fails++;limits.set(binds[0],r);
   }
   return {success:true};
  }
 };}};
 return {DB,KEY_PEPPER:pepper,ASSETS:{fetch:()=>new Response('ok')},_docs:docs};
}
function req(path,method='GET',body=null,cookie='',origin=ORIGIN){
 const headers={...(method==='POST'?{'content-type':'application/json',origin}:{}),...(cookie?{cookie}:{})};
 return new Request(ORIGIN+path,{method,headers,...(body===null?{}:{body:JSON.stringify(body)})});
}
async function call(env,path,method='GET',body=null,cookie='',origin=ORIGIN){
 const r=await worker.fetch(req(path,method,body,cookie,origin),env);
 return {status:r.status,body:await r.json(),cookie:r.headers.get('set-cookie')};
}
async function signIn(env,alias,canonical){
 const r=await call(env,'/api/login','POST',{username:alias,secret:secrets[canonical]});
 assert.equal(r.status,200,JSON.stringify(r.body));
 assert.deepEqual(r.body.user,{username:canonical,displayName:LABELS[canonical]});
 return r.cookie.split(';')[0];
}

test('state schema',()=>{
 assert.equal(checkDocument(fixture()),true);
 assert.equal(checkDocument({version:4,projects:[]}),false);
});

test('existing credentials work via new names; missing auth and wrong secret rejected',async()=>{
 const env=environment();
 assert.equal((await call(env,'/api/state')).status,401);
 assert.equal((await call(env,'/api/login','POST',{username:'炮台',secret:secrets.admin02})).status,401);
 assert.equal((await call(env,'/api/login','POST',{username:'炮台',secret:secrets.admin01},'','https://evil.test')).status,403);
 for(const [canonical,alias] of Object.entries(LABELS)){
  const cookie=await signIn(env,alias,canonical);
  const me=await call(env,'/api/me','GET',null,cookie);
  assert.deepEqual(me.body.user,{username:canonical,displayName:alias});
  const own=await call(env,'/api/state','GET',null,cookie);
  assert.equal(own.status,200);assert.equal(own.body.owner,canonical);assert.equal(own.body.editable,true);
  assert.equal(own.body.state.projects[0].name,'旧共享资料');
  assert.equal((await call(env,'/api/logout','POST',{},cookie)).status,200);
  assert.equal((await call(env,'/api/state','GET',null,cookie)).status,401);
 }
});

test('own writes isolated; cross-account reads allowed; cross-account writes rejected by Worker',async()=>{
 const env=environment();
 const a=await signIn(env,'炮台','admin01');
 const b=await signIn(env,'芋头','admin02');
 const c=await signIn(env,'EE','admin03');
 const change=fixture('炮台专属', '0.013456789012');
 const posted=await call(env,'/api/state','POST',{state:change},a);
 assert.equal(posted.status,200);assert.equal(posted.body.owner,'admin01');
 const aData=await call(env,'/api/state','GET',null,a);
 const bData=await call(env,'/api/state','GET',null,b);
 assert.equal(aData.body.state.projects[0].name,'炮台专属');
 assert.equal(bData.body.state.projects[0].name,'旧共享资料');
 const viewed=await call(env,'/api/state?owner=admin01','GET',null,b);
 assert.equal(viewed.status,200);assert.equal(viewed.body.editable,false);
 assert.equal(viewed.body.state.projects[0].name,'炮台专属');
 assert.equal((await call(env,'/api/state?owner=admin01','POST',{state:fixture('恶意覆盖')},b)).status,403);
 assert.equal((await call(env,'/api/state','POST',{owner:'admin01',state:fixture('恶意覆盖')},b)).status,403);
 assert.equal((await call(env,'/api/state?owner=ghost','GET',null,b)).status,400);
 assert.equal((await call(env,'/api/state/sync','POST',{source:'admin01'},'', 'https://evil.test')).status,403);
 const verify=await call(env,'/api/state','GET',null,a);
 assert.equal(verify.body.state.projects[0].name,'炮台专属');
 const cData=await call(env,'/api/state','GET',null,c);
 assert.equal(cData.body.state.projects[0].name,'旧共享资料');
});

test('explicit copy atomically overwrites only requester; source unchanged; revision increments',async()=>{
 const env=environment();
 const a=await signIn(env,'炮台','admin01');
 const b=await signIn(env,'芋头','admin02');
 const c=await signIn(env,'EE','admin03');
 assert.equal((await call(env,'/api/state','POST',{state:fixture('炮台商品')},a)).status,200);
 assert.equal((await call(env,'/api/state','POST',{state:fixture('芋头商品')},b)).status,200);
 const before=(await call(env,'/api/state','GET',null,b)).body.revision;
 assert.equal((await call(env,'/api/state/sync','POST',{source:'芋头'},b)).status,400,'self copy denied');
 assert.equal((await call(env,'/api/state/sync','POST',{source:'nobody'},b)).status,400);
 const copied=await call(env,'/api/state/sync','POST',{source:'炮台'},b);
 assert.equal(copied.status,200,JSON.stringify(copied.body));
 assert.equal(copied.body.owner,'admin02');
 assert.equal(copied.body.revision,before+1);
 const bAfter=(await call(env,'/api/state','GET',null,b)).body.state;
 const aAfter=(await call(env,'/api/state','GET',null,a)).body.state;
 const cAfter=(await call(env,'/api/state','GET',null,c)).body.state;
 assert.equal(bAfter.projects[0].name,'炮台商品');
 assert.equal(aAfter.projects[0].name,'炮台商品');
 assert.equal(cAfter.projects[0].name,'旧共享资料');
 assert.equal((await call(env,'/api/state','POST',{state:fixture('芋头新编辑')},b)).status,200);
 assert.equal((await call(env,'/api/state','GET',null,a)).body.state.projects[0].name,'炮台商品');
});

test('missing migration cannot silently save elsewhere; source without saved state cannot overwrite',async()=>{
 const env=environment({legacy:null});
 const a=await signIn(env,'炮台','admin01');
 const b=await signIn(env,'芋头','admin02');
 assert.equal((await call(env,'/api/state/sync','POST',{source:'admin01'},b)).status,409);
 assert.equal((await call(env,'/api/state','POST',{state:fixture('保存')},a)).status,200);
 const ownB=(await call(env,'/api/state','GET',null,b)).body;
 assert.equal(ownB.state,null);
 env._docs.delete('fixed-account-2');
 assert.equal((await call(env,'/api/state','GET',null,b)).status,503);
 assert.equal((await call(env,'/api/state','POST',{state:fixture('不能写')},b)).status,503);
});
