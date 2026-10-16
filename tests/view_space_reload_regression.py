"""Browser regression: read-only browsing and persisted view-owner preference.
No live Worker or D1 is called. The restricted CI browser cannot navigate,
so a page refresh is simulated by replacing the DOM, reloading the app script,
and retaining browser-like localStorage in memory.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json

ROOT=Path(__file__).resolve().parent.parent
html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()

def make_state(owner):
    return {
        'version':4,
        'currentProjectId':f'{owner}-project1',
        'projects': [
            { 'id':f'{owner}-project1','name':f'{owner} 项目甲','costItems':[],
              'currentPackageId':f'{owner}-pack1',
              'packages':[
                  {'id':f'{owner}-pack1','name':'套餐 A','products':[], 'fees':[], 'discounts':[{'id':'discount-a','zhe':'6'}]},
                  {'id':f'{owner}-pack2','name':'套餐 B','products':[], 'fees':[], 'discounts':[{'id':'discount-b','zhe':'7'}]},
              ]},
            { 'id':f'{owner}-project2','name':f'{owner} 项目乙','costItems':[],
              'currentPackageId':f'{owner}-pack3',
              'packages':[
                  {'id':f'{owner}-pack3','name':'套餐 C','products':[], 'fees':[], 'discounts':[{'id':'discount-c','zhe':'6.5'}]},
                  {'id':f'{owner}-pack4','name':'套餐 D','products':[], 'fees':[], 'discounts':[{'id':'discount-d','zhe':'8'}]},
              ]}
        ]
    }
mock_docs={username:make_state(username) for username in ('admin01','admin02','admin03')}
init_js='''(docs)=>{
  // Chromium in this test environment blocks all navigation, including localhost.
  // Persist an in-memory localStorage across reinitializing the page document.
  const originals=docs;
  const prefs={};
  Object.defineProperty(window,'localStorage',{configurable:true,value:{
    getItem:(k)=>Object.hasOwn(prefs,k)?prefs[k]:null,
    setItem:(k,v)=>{prefs[k]=String(v);},
    removeItem:(k)=>{delete prefs[k];}
  }});
  window.setInterval=()=>0;
  window.__getMockData=()=>JSON.parse(localStorage.getItem('__mock_cloud_docs')||JSON.stringify(originals));
  const respond=(json,code=200)=>Promise.resolve(new Response(JSON.stringify(json),{status:code,headers:{'content-type':'application/json'}}));
  window.fetch=(path,options={})=>{
    if(!String(path).startsWith('/api/'))return Promise.reject(new Error('No external requests expected'));
    const currentUser=localStorage.getItem('__mock_signed_in')||'admin01';
    const logs=JSON.parse(localStorage.getItem('__mock_api_log')||'[]');
    logs.push({url:path,method:options.method||'GET',who:currentUser});
    localStorage.setItem('__mock_api_log',JSON.stringify(logs));
    if(path==='/api/me')return respond({ok:true,user:{username:currentUser}});
    if(path==='/api/logout')return respond({ok:true});
    if(path==='/api/login')return respond({ok:true,user:{username:currentUser}});
    if(path==='/api/state' && options.method==='POST')return respond({ok:true,revision:2});
    if(path.startsWith('/api/state?owner=')){
      const owner=path.split('owner=')[1];
      const docs=window.__getMockData();
      if(!docs[owner])return respond({ok:false,message:'No such owner'},404);
      return respond({ok:true,owner,revision:1,state:docs[owner]});
    }
    return respond({ok:false,message:'Bad route'},404);
  };
}'''
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded')
    page.add_style_tag(content=css)
    page.evaluate(f'({init_js})({json.dumps(mock_docs,ensure_ascii=False)})')
    def simulate_reload():
        # Rebuild DOM and rerun app bootstrap; shared memory preferences
        # survive like localStorage across page refresh.
        page.set_content(html,wait_until='domcontentloaded')
        page.add_style_tag(content=css)
        page.add_script_tag(content=js)
    page.add_script_tag(content=js)
    page.locator('#authGate').wait_for(state='hidden')
    assert page.locator('#viewOwnerSelect').input_value()=='admin01'
    assert page.locator('#saveBtn').is_visible()
    assert page.locator('#packageSelect').is_enabled()
    # Switch to another account's read-only space.
    page.locator('#viewOwnerSelect').select_option('admin02')
    page.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin02" && document.querySelector("#spaceBusy").hidden')
    assert page.locator('#spaceBadge').is_visible()
    assert page.locator('#saveBtn').is_hidden()
    assert page.locator('#dataMenu').is_hidden()
    assert page.locator('#packageSelect').is_enabled(), 'read-only package browsing was disabled'
    assert page.locator('#projectSelect').is_enabled(), 'read-only project browsing should stay enabled'
    # Change packages and projects without mutating server data.
    page.locator('[data-nav="pricing"]').click()
    page.locator('#packageSelect').select_option('admin02-pack2')
    assert page.locator('#metricPackageName').inner_text()=='套餐 B'
    page.locator('#projectSelect').select_option('admin02-project2')
    page.locator('#packageSelect').select_option('admin02-pack4')
    assert page.locator('#metricPackageName').inner_text()=='套餐 D'
    assert page.evaluate('localStorage.getItem("dopamine-cloud-last-view-owner-admin01")')=='admin02'
    assert page.evaluate('JSON.parse(localStorage.getItem("__mock_api_log")).every(x=>x.method!=="POST")'), 'read-only browsing must never POST'
    # Document-reinitialization F5 equivalent (navigation blocked by container policy). Must restore other space and its browser-only selections.
    simulate_reload()
    page.locator('#authGate').wait_for(state='hidden')
    page.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin02"')
    page.locator('[data-nav="pricing"]').click()
    assert page.locator('#projectSelect').input_value()=='admin02-project2'
    assert page.locator('#packageSelect').input_value()=='admin02-pack4'
    assert page.locator('#metricPackageName').inner_text()=='套餐 D'
    assert page.locator('#saveBtn').is_hidden()
    assert page.locator('#dataMenu').is_hidden()
    assert page.locator('#packageSelect').is_enabled()
    assert page.evaluate('window.__getMockData().admin02.projects[1].currentPackageId')=='admin02-pack3', 'view selection must not change server-side business data'
    # Switching back to own space and reloading should remain there.
    page.locator('#viewOwnerSelect').select_option('admin01')
    page.wait_for_function('document.querySelector("#saveBtn").hidden === false && document.querySelector("#spaceBusy").hidden')
    simulate_reload()
    page.locator('#authGate').wait_for(state='hidden')
    assert page.locator('#viewOwnerSelect').input_value()=='admin01'
    assert page.locator('#saveBtn').is_visible()
    assert page.locator('#dataMenu').is_visible()
    # Preferences are per signed-in user; switching login cannot leak a different user's view.
    page.evaluate('localStorage.setItem("__mock_signed_in","admin03")')
    simulate_reload()
    page.locator('#authGate').wait_for(state='hidden')
    assert page.locator('#viewOwnerSelect').input_value()=='admin03'
    assert page.locator('#saveBtn').is_visible()
    assert page.locator('#packageSelect').is_enabled()
    assert not errors,errors
    browser.close()
    print('PASS: cross-account read-only package/project switches + simulated document reload restores viewer and selections; zero writes; owner-scoped preference')
