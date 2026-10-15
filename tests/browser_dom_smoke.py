from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
html=(ROOT/'index.html').read_text()
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()
with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-extensions'])
  page=browser.new_page(viewport={'width':1366,'height':768})
  errors=[]
  page.on('pageerror',lambda e: errors.append(str(e)))
  page.set_content(html.replace('<script defer="" src="./app.js"></script>',''),wait_until='domcontentloaded')
  page.add_style_tag(content=css)
  page.add_script_tag(content='''
  window.__cloudMock={authed:false,state:null,rev:0,saves:0};
  window.fetch=async (url,options={})=>{
    const m=window.__cloudMock;
    const respond=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
    if (url.endsWith('/api/me')) return m.authed?respond({ok:true,user:{username:'admin01'}}):respond({message:'请先登录'},401);
    if (url.endsWith('/api/login')){m.authed=true;return respond({ok:true,user:{username:'admin01'}});}
    if (url.endsWith('/api/logout')){m.authed=false;return respond({ok:true});}
    if (url.endsWith('/api/state') && options.method==='POST'){
      m.state=JSON.parse(options.body).state;m.rev++;m.saves++;return respond({ok:true,revision:m.rev,updatedAt:Date.now(),updatedBy:'admin01'});
    }
    if (url.endsWith('/api/state'))return respond({ok:true,state:m.state,revision:m.rev,updatedAt:Date.now()});
    return respond({message:'missing'},404);
  };
  ''')
  page.add_script_tag(content=js)
  page.locator('#authGate').wait_for(state='visible')
  page.locator('#loginUsername').fill('admin01')
  page.locator('#loginSecret').fill('abcdefghijklmnopqrstuvwx12345678')
  page.locator('#loginSubmit').click()
  page.locator('#authGate').wait_for(state='hidden',timeout=5000)
  page.locator('#addCostItemBtn').click()
  page.locator('#saveBtn').click()
  page.wait_for_function('window.__cloudMock.saves===1')
  assert len(page.evaluate('window.__cloudMock.state.projects[0].costItems'))==1
  page.locator('#logoutBtn').click()
  page.locator('#authGate').wait_for(state='visible')
  assert not errors,errors
  print('Browser DOM smoke PASS: login, editable UI, Worker state save, logout')
  browser.close()
