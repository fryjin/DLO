const te = new TextEncoder();
const MAX_DOCUMENT_BYTES = 850_000;
const SESSION_SECONDS = 7 * 24 * 3600;
const LOGIN_WINDOW_MS = 15 * 60_000;
const MAX_ATTEMPTS = 6;

function respond(data, status=200, extraHeaders={}) {
  return new Response(JSON.stringify(data), {
    status, headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff',...extraHeaders}
  });
}
function fail(status, code, message) { return respond({ok:false,code,message},status); }
function keyBytes(value) { return te.encode(value); }
function toHex(bytes) { return [...new Uint8Array(bytes)].map(v=>v.toString(16).padStart(2,'0')).join(''); }
async function sha256(value) { return toHex(await crypto.subtle.digest('SHA-256',keyBytes(value))); }
async function hmacHex(secret, text) {
  const key=await crypto.subtle.importKey('raw',keyBytes(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return toHex(await crypto.subtle.sign('HMAC',key,keyBytes(text)));
}
function equalHex(a,b) {
  if (!/^[0-9a-f]{64}$/.test(a || '') || !/^[0-9a-f]{64}$/.test(b || '')) return false;
  const aa=new Uint8Array(a.match(/../g).map(h=>parseInt(h,16)));
  const bb=new Uint8Array(b.match(/../g).map(h=>parseInt(h,16)));
  let diff=0; for(let i=0;i<aa.length;i++) diff|=(aa[i]^bb[i]); return diff===0;
}
function cookieValue(request,name) {
  const cookies=(request.headers.get('cookie')||'').split(';');
  const found=cookies.map(s=>s.trim()).find(c=>c.startsWith(name+'='));
  return found ? found.slice(name.length+1):null;
}
function randomToken() {
  const bytes=crypto.getRandomValues(new Uint8Array(32));
  // URL-safe hex avoids reliance on btoa and has 256 bits of entropy.
  return toHex(bytes);
}
function cookieHeader(value,expire=false) {
  return `dopamine_session=${expire?'':value}; Path=/; HttpOnly; Secure; SameSite=Lax; ${expire?'Max-Age=0':'Max-Age='+SESSION_SECONDS}`;
}
async function auth(request,env) {
  const token=cookieValue(request,'dopamine_session');
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return null;
  const hash=await sha256(token);
  const row=await env.DB.prepare(`SELECT users.id,users.username FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=? AND sessions.expires_at>? AND users.enabled=1`).bind(hash,Date.now()).first();
  return row || null;
}
function safeName(name) { return typeof name==='string' && name.length>0 && name.length<=80; }
function checkDocument(obj) {
  if (!obj || typeof obj !== 'object' || obj.version !== 4 || !Array.isArray(obj.projects) || obj.projects.length<1 || obj.projects.length>250) return false;
  if (!obj.projects.every(p => p && safeName(p.name) && typeof p.id==='string' && Array.isArray(p.costItems) && Array.isArray(p.packages) && p.packages.length>0)) return false;
  if (!obj.projects.some(p=>p.id===obj.currentProjectId)) return false;
  for (const p of obj.projects) {
    if (p.costItems.length>10_000 || p.packages.length>2_000) return false;
    if (!p.packages.some(x=>x.id===p.currentPackageId)) return false;
    if (!p.packages.every(x=>x && safeName(x.name) && Array.isArray(x.products) && Array.isArray(x.fees) && Array.isArray(x.discounts) && x.products.length<=10_000 && x.fees.length<=3_000 && x.discounts.length<=250)) return false;
  }
  return true;
}
async function readJSON(request,maxBytes=MAX_DOCUMENT_BYTES) {
  const len=Number(request.headers.get('content-length')||0);
  if (len>maxBytes) throw new Error('PAYLOAD_TOO_LARGE');
  const raw=await request.text();
  if (te.encode(raw).length>maxBytes) throw new Error('PAYLOAD_TOO_LARGE');
  try {return JSON.parse(raw);} catch {throw new Error('INVALID_JSON');}
}
async function login(request,env) {
  let body;
  try {body=await readJSON(request,2500);} catch {return fail(400,'INVALID_INPUT','账号或密钥格式不正确');}
  const username=String(body?.username||'').trim().toLowerCase();
  const secret=String(body?.secret||'');
  if (!/^[a-z0-9_-]{3,32}$/.test(username) || secret.length<24 || secret.length>256) return fail(401,'LOGIN_FAILED','账号或密钥不正确');
  if (!env.KEY_PEPPER || env.KEY_PEPPER.length<32) return fail(503,'SETUP_REQUIRED','尚未配置登录安全密钥');

  const now=Date.now();
  const lock=await env.DB.prepare('SELECT fails,window_start FROM login_limits WHERE username=?').bind(username).first();
  if (lock && now-lock.window_start<LOGIN_WINDOW_MS && lock.fails>=MAX_ATTEMPTS) return fail(429,'LOGIN_LOCKED','尝试次数过多，请15分钟后重试');
  const user=await env.DB.prepare('SELECT id,username,secret_hash,enabled FROM users WHERE username=?').bind(username).first();
  // Keyed hashing is appropriate here because secrets are 32 cryptographically random bytes,
  // not human-selected passwords. It avoids costly PBKDF2 on the Workers Free CPU budget.
  const digest=await hmacHex(env.KEY_PEPPER,username+':'+secret);
  if (!user || !user.enabled || !equalHex(digest,user.secret_hash)) {
    await env.DB.prepare(`INSERT INTO login_limits(username,fails,window_start) VALUES(?,1,?)
      ON CONFLICT(username) DO UPDATE SET fails=CASE WHEN ?-window_start>=? THEN 1 ELSE fails+1 END,
      window_start=CASE WHEN ?-window_start>=? THEN ? ELSE window_start END`)
      .bind(username,now,now,LOGIN_WINDOW_MS,now,LOGIN_WINDOW_MS,now).run();
    return fail(401,'LOGIN_FAILED','账号或密钥不正确');
  }
  await env.DB.prepare('DELETE FROM login_limits WHERE username=?').bind(username).run();
  const token=randomToken();
  const tokenHash=await sha256(token);
  await env.DB.prepare('INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)').bind(tokenHash,user.id,now+SESSION_SECONDS*1000,now).run();
  return respond({ok:true,user:{username:user.username}},200,{'set-cookie':cookieHeader(token)});
}
async function logout(request,env) {
  const token=cookieValue(request,'dopamine_session');
  if (token && /^[a-f0-9]{64}$/.test(token)) {
    await env.DB.prepare('DELETE FROM sessions WHERE token_hash=?').bind(await sha256(token)).run();
  }
  return respond({ok:true},200,{'set-cookie':cookieHeader('',true)});
}
async function getState(env) {
  const row=await env.DB.prepare("SELECT data_json,version,updated_at,updated_by FROM shared_document WHERE id='main'").first();
  return respond({ok:true,state:row?.data_json?JSON.parse(row.data_json):null,revision:row?.version||0,updatedAt:row?.updated_at||null,updatedBy:row?.updated_by||null});
}
async function putState(request,env,user) {
  let body;
  try {body=await readJSON(request);} catch(e) {return fail(e.message==='PAYLOAD_TOO_LARGE'?413:400,e.message,'数据格式无效或过大');}
  if (!checkDocument(body?.state)) return fail(400,'INVALID_STATE','项目数据校验未通过');
  const raw=JSON.stringify(body.state);
  if (te.encode(raw).length>MAX_DOCUMENT_BYTES) return fail(413,'PAYLOAD_TOO_LARGE','数据超过当前免费方案允许的大小');
  const now=Date.now();
  // Explicit whole-document Last-Write-Wins. Atomic UPDATE gives a server-issued revision.
  const row=await env.DB.prepare(`UPDATE shared_document SET data_json=?,version=version+1,updated_at=?,updated_by=? WHERE id='main' RETURNING version,updated_at,updated_by`)
    .bind(raw,now,user.username).first();
  return respond({ok:true,revision:row.version,updatedAt:row.updated_at,updatedBy:row.updated_by});
}
function sameOriginPost(request) {
  const origin=request.headers.get('origin');
  // Mutation requests from a browser must be same-origin, preventing cookie CSRF.
  // A missing Origin is rejected except from local CLI health tooling (no mutation allowed).
  return !!origin && origin === new URL(request.url).origin;
}
async function api(request,env) {
  const path=new URL(request.url).pathname;
  const method=request.method;
  if (!env.DB) return fail(503,'DB_NOT_CONFIGURED','数据库未绑定');
  if (method==='POST' && !sameOriginPost(request)) return fail(403,'FORBIDDEN_ORIGIN','请求来源不受信任');
  if (path==='/api/login' && method==='POST') return login(request,env);
  if (path==='/api/logout' && method==='POST') return logout(request,env);
  const user=await auth(request,env);
  if (!user) return fail(401,'UNAUTHORIZED','请先登录');
  if (path==='/api/me' && method==='GET') return respond({ok:true,user:{username:user.username}});
  if (path==='/api/state' && method==='GET') return getState(env);
  if (path==='/api/state' && method==='POST') return putState(request,env,user);
  return fail(404,'NOT_FOUND','接口不存在');
}
export default {
  async fetch(request,env) {
    const path=new URL(request.url).pathname;
    try {
      if (path.startsWith('/api/')) return api(request,env);
      if (!['GET','HEAD'].includes(request.method)) return new Response('Method Not Allowed',{status:405});
      const response=await env.ASSETS.fetch(request);
      const headers=new Headers(response.headers);
      headers.set('x-content-type-options','nosniff');
      headers.set('referrer-policy','strict-origin-when-cross-origin');
      headers.set('permissions-policy','camera=(), microphone=(), geolocation=()');
      headers.set('content-security-policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'");
      if (path==='/' || path.endsWith('.html')) headers.set('cache-control','no-store');
      return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
    } catch(error) {
      console.error('Dopamine Worker error',error?.message||'unknown');
      return path.startsWith('/api/') ? fail(500,'SERVER_ERROR','服务器暂时不可用，请稍后重试') : new Response('Service unavailable',{status:503});
    }
  }
};
export {checkDocument};
