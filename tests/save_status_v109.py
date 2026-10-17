"""V1.0.9 save-state regression in simulated Cloud Worker browser environment."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='domcontentloaded')
    page.add_style_tag(content=css)
    page.add_script_tag(content='''
      window.__test={writes:[],reads:[],rev:0,doc:null,timers:[]};
      window.setInterval=(fn,delay)=>{window.__test.timers.push({fn,delay});return 1;};
      window.fetch=async(url,options={})=>{
        const t=window.__test;
        const reply=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json'}});
        if(url==='/api/me')return reply({ok:true,user:{username:'admin01',displayName:'炮台'}});
        if(url==='/api/state'&&options.method==='POST'){
          const value=JSON.parse(options.body).state;
          t.doc=value;t.rev++;t.writes.push({rev:t.rev,at:Date.now(),value});
          return reply({ok:true,revision:t.rev,updatedAt:Date.now()});
        }
        if(url.startsWith('/api/state')){
          t.reads.push(url);
          return reply({ok:true,revision:t.rev,state:t.doc,updatedAt:t.doc?Date.now():null});
        }
        return reply({ok:false,message:'Not found'},404);
      };
    ''')
    page.add_script_tag(content=js)
    page.locator('#authGate').wait_for(state='hidden')
    assert '就绪' in page.locator('#saveState').inner_text()
    assert len(page.evaluate('window.__test.timers'))==1
    assert page.evaluate('window.__test.timers[0].delay')==300000
    page.locator('#addCostItemBtn').click()
    page.locator('.cost-name-input').first.fill('保存状态测试')
    assert '未保存' in page.locator('#saveState').inner_text()
    page.locator('#saveBtn').click()
    page.wait_for_function('window.__test.writes.length===1')
    page.wait_for_function('document.querySelector("#saveState").dataset.status==="manual"')
    assert page.locator('#saveState').inner_text().startswith('手动保存 '),page.locator('#saveState').inner_text()
    manual_time=page.locator('#saveState').inner_text().split(' ')[-1]
    assert len(manual_time)==5 and ':' in manual_time
    page.locator('.cost-name-input').first.fill('保存状态测试-自动')
    assert '未保存' in page.locator('#saveState').inner_text()
    page.evaluate('window.__test.timers[0].fn()')
    page.wait_for_function('window.__test.writes.length===2')
    page.wait_for_function('document.querySelector("#saveState").dataset.status==="auto"')
    assert page.locator('#saveState').inner_text().startswith('自动保存 '),page.locator('#saveState').inner_text()
    page.evaluate('window.__test.timers[0].fn()')
    page.wait_for_function('window.__test.reads.length>=3')
    assert page.evaluate('window.__test.writes.length')==2,'A clean interval must not overwrite server data'
    assert page.locator('#saveState').inner_text().startswith('自动保存 '),'A read-only sync must not fabricate another save'
    # Narrower views should no longer hide the save-time status.
    page.set_viewport_size({'width':900,'height':850})
    assert page.locator('#saveState').is_visible(),'Save feedback must remain visible on compact screens'
    # Viewed accounts remain read-only and must never auto-post to owner.
    page.locator('#viewOwnerSelect').select_option('admin02')
    page.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin02" && document.querySelector("#spaceBusy").hidden')
    assert '只读浏览' in page.locator('#saveState').inner_text()
    page.evaluate('window.__test.timers[0].fn()')
    page.wait_for_timeout(100)
    assert page.evaluate('window.__test.writes.length')==2
    assert not errors,errors
    browser.close()
print('PASS: manual/auto timestamps, 5m scheduler, no redundant writes, compact visible, read-only guard')
