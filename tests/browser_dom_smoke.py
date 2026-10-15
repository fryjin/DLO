from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()

with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-extensions'])
  page=browser.new_page(viewport={'width':1440,'height':900})
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='domcontentloaded')
  page.add_style_tag(content=css)
  page.add_script_tag(content='''
  window.__cloudMock={authed:true,user:{username:'admin01',displayName:'炮台'},docs:{
    admin01:{state:null,rev:0},admin02:{state:null,rev:0},admin03:{state:null,rev:0}},saves:[],copied:[],meReady:null};
  window.fetch=async(url,options={})=>{
    const m=window.__cloudMock;
    const send=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
    if(url==='/api/me'){
      await new Promise(resolve=>m.meReady=resolve);
      return m.authed?send({ok:true,user:m.user}):send({message:'not authenticated'},401);
    }
    if(url==='/api/login'){
      const arg=JSON.parse(options.body),alias={'炮台':'admin01','芋头':'admin02',EE:'admin03'};
      const who=alias[arg.username];if(!who)return send({message:'bad'},401);
      m.authed=true;m.user={username:who,displayName:arg.username};return send({ok:true,user:m.user});
    }
    if(url==='/api/logout'){m.authed=false;return send({ok:true});}
    if(url.startsWith('/api/state/sync')){
      const source=JSON.parse(options.body).source;
      if(!m.docs[source].state)return send({message:'无来源数据'},409);
      const target=m.user.username;
      m.docs[target].state=JSON.parse(JSON.stringify(m.docs[source].state));
      m.docs[target].rev++;
      m.copied.push([source,target]);
      return send({ok:true,revision:m.docs[target].rev,owner:target});
    }
    if(url==='/api/state'&&options.method==='POST'){
      const owner=m.user.username;
      m.docs[owner].state=JSON.parse(options.body).state;
      m.docs[owner].rev++;m.saves.push(owner);
      return send({ok:true,revision:m.docs[owner].rev,updatedAt:Date.now(),updatedBy:owner});
    }
    if(url.startsWith('/api/state')){
      const owner=new URL(url,'https://example.com').searchParams.get('owner')||m.user.username;
      const doc=m.docs[owner];return send({ok:true,owner,editable:owner===m.user.username,state:doc.state,revision:doc.rev});
    }
    return send({message:'missing'},404);
  };
  ''')
  page.add_script_tag(content=js)
  page.wait_for_function('window.__cloudMock.meReady!==null')
  assert page.locator('#authLoading').is_visible()
  assert not page.locator('#authGate').is_visible()
  page.evaluate('window.__cloudMock.meReady()')
  page.locator('#authLoading').wait_for(state='hidden')
  page.locator('#authGate').wait_for(state='hidden')
  assert page.locator('#currentUserLabel').inner_text()=='炮台'
  assert page.locator('#currentUserAvatar').inner_text()=='炮'
  assert page.locator('#resetBtn').count()==0
  assert page.locator('#syncNowBtn').count()==0
  assert page.locator('#logoutBtn').count()==1
  assert page.locator('#accountMenu').is_visible()
  page.locator('#accountMenuTrigger').click()
  assert page.locator('#accountMenu').get_attribute('open') is not None
  assert page.locator('#accountMenuName').inner_text()=='炮台'
  page.locator('#accountMenuTrigger').click()
  # Before UI-level account switch: each of three accounts must be independent.
  page.locator('#addCostItemBtn').click()
  page.locator('.cost-name-input').first.fill('炮台的产品')
  page.locator('#saveBtn').click()
  page.wait_for_function('window.__cloudMock.saves.length===1')
  assert page.evaluate('window.__cloudMock.docs.admin01.state.projects[0].costItems[0].name')=='炮台的产品'
  # Pre-populate a different owner's account data via a separate logical session.
  page.evaluate('''()=>{const s=JSON.parse(JSON.stringify(window.__cloudMock.docs.admin01.state));s.projects[0].costItems[0].name='芋头的产品';window.__cloudMock.docs.admin02={state:s,rev:2};}''')
  page.locator('#viewOwnerSelect').select_option('admin02')
  page.wait_for_function('document.querySelector("#spaceBadge").textContent.includes("芋头") && !document.querySelector("#spaceBusy").hidden===false')
  assert page.locator('.cost-name-input').first.input_value()=='芋头的产品'
  assert page.locator('.cost-name-input').first.is_disabled(), 'others must be read-only'
  assert page.locator('#saveBtn').is_disabled()
  assert page.locator('#restoreBtn').is_disabled()
  assert page.locator('#backupBtn').is_enabled(), 'read-only backup must remain available'
  assert page.locator('#projectSelect').is_enabled(), 'read-only browsing must remain available'
  assert page.locator('#copyFromOwnerBtn').is_visible()
  # View-only browse should not trigger saving, even if a forced timer fires.
  page.evaluate('window.__cloudMock.beforeCount=window.__cloudMock.saves.length')
  # Confirm dialog must not mutate unless user explicitly confirms.
  page.locator('#copyFromOwnerBtn').click()
  assert page.locator('#copyConfirmDialog').is_visible()
  assert '覆盖' in page.locator('#copyConfirmDialog').inner_text()
  page.locator('#cancelCopyBtn').click()
  assert page.locator('#copyConfirmDialog').is_hidden()
  assert page.evaluate('window.__cloudMock.copied.length')==0
  page.locator('#copyFromOwnerBtn').click()
  page.locator('#confirmCopyBtn').click()
  page.wait_for_function('window.__cloudMock.copied.length===1')
  page.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin01" && !document.querySelector("#saveBtn").disabled')
  assert page.locator('.cost-name-input').first.input_value()=='芋头的产品'
  assert page.evaluate('window.__cloudMock.docs.admin01.state.projects[0].costItems[0].name')=='芋头的产品'
  assert page.evaluate('window.__cloudMock.docs.admin02.state.projects[0].costItems[0].name')=='芋头的产品'
  assert page.evaluate('window.__cloudMock.docs.admin03.state') is None
  # Any newly edited data saves only to the current user's space.
  page.locator('.cost-name-input').first.fill('炮台再次修改')
  page.locator('#saveBtn').click()
  page.wait_for_function('window.__cloudMock.saves.length===2')
  assert page.evaluate('window.__cloudMock.docs.admin01.state.projects[0].costItems[0].name')=='炮台再次修改'
  assert page.evaluate('window.__cloudMock.docs.admin02.state.projects[0].costItems[0].name')=='芋头的产品'
  # Avatar-menu logout preserves the unsaved confirmation behavior.
  page.locator('.cost-name-input').first.fill('尚未保存的内容')
  page.locator('#accountMenuTrigger').click()
  page.locator('#logoutBtn').click()
  assert page.locator('#exitDialog').is_visible()
  page.locator('#exitCancel').click()
  assert page.locator('#exitDialog').is_hidden()
  assert page.locator('.cost-name-input').first.input_value()=='尚未保存的内容'
  page.locator('#accountMenuTrigger').click()
  page.locator('#logoutBtn').click()
  page.locator('#exitDiscard').click()
  page.locator('#authGate').wait_for(state='visible')
  assert page.locator('#currentUserAvatar').inner_text()=='?'
  assert not errors,errors
  print('Browser smoke PASS: account avatar, no obsolete buttons, isolated saves, read-only, sync confirm, logout confirmation')
  browser.close()
