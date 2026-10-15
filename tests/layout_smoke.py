from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-extensions'])
 for width in [1920,1440,1280,1024,768]:
  p=b.new_page(viewport={'width':width,'height':900})
  p.set_content(html)
  p.add_style_tag(content=css)
  p.add_script_tag(content='''
  window.fetch=async (url,options={})=>{
    const send=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'content-type':'application/json'}});
    if(url==='/api/me')return send({ok:true,user:{username:'admin01',displayName:'炮台'}});
    if(url.startsWith('/api/state'))return send({ok:true,revision:1,owner:'admin01',state:null});
    return send({ok:true});
  };''')
  p.add_script_tag(content=js)
  p.locator('#authLoading').wait_for(state='hidden')
  p.screenshot(path=str(ROOT/f'tests/layout_{width}.png'))
  positions=p.evaluate('''()=>{const ids=['projectSelect','viewOwnerSelect','saveState','saveBtn','currentUserAvatar'];return ids.map(id=>{let r=document.getElementById(id).getBoundingClientRect();return [id,Math.round(r.left),Math.round(r.right),Math.round(r.top),Math.round(r.bottom)]})}''')
  a=next(x for x in positions if x[0]=='currentUserAvatar')
  assert a[1]>=0 and a[2]<=width, f'avatar clipped at {width}: {a}'
  assert a[3]>=0 and a[4]<=900, f'avatar missing at {width}: {a}'
  p.locator('#accountMenuTrigger').click()
  assert p.locator('#logoutBtn').is_visible(),f'logout menu hidden at {width}'
  menu=p.locator('.sidebar-account-popover').bounding_box()
  assert menu['x']>=0 and menu['x']+menu['width']<=width,f'account menu clipped at {width}: {menu}'
  assert menu['y']>=0 and menu['y']+menu['height']<=900,f'account menu offscreen at {width}: {menu}'
  p.screenshot(path=str(ROOT/f'tests/menu_{width}.png'))
  print(width,positions, 'account menu',menu)

  p.close()
 b.close()
