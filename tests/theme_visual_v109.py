"""Visual smoke capture for color palette, saving state and compact layouts."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests'/'captures_v109';OUT.mkdir(exist_ok=True)
html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
css=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text()
js=(ROOT/'app.js').read_text()
for width,height in ((1440,900),(1024,768),(900,768)):
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
  page.set_content(html,wait_until='domcontentloaded')
  page.add_style_tag(content=css)
  page.add_script_tag(content='''
  window.__mockDoc=null; window.__revision=0;
  window.fetch=async(url,opts={})=>{
    let result={ok:true};
    if(url==='/api/me')result.user={username:'admin01',displayName:'炮台'};
    else if(url==='/api/state'&&opts.method==='POST'){
      window.__mockDoc=JSON.parse(opts.body).state;window.__revision++;
      result={ok:true,revision:window.__revision,updatedAt:Date.now()};
    }
    else if(url.startsWith('/api/state'))result={ok:true,state:window.__mockDoc,revision:window.__revision,updatedAt:window.__revision?Date.now():null};
    return new Response(JSON.stringify(result),{status:200,headers:{'content-type':'application/json'}});
  };''')
  page.add_script_tag(content=js)
  page.locator('#authGate').wait_for(state='hidden')
  page.locator('#addCostItemBtn').click()
  page.locator('.cost-name-input').first.fill('复古吊牌 A')
  page.locator('.cost-value-input').first.fill('0.12')
  page.locator('.cost-value-input').first.press('Tab')
  page.locator('.cost-list-price-input').first.fill('0.28')
  page.locator('.cost-list-price-input').first.press('Tab')
  page.locator('#addCostItemBtn').click()
  page.locator('.cost-name-input').nth(1).fill('暖色贴纸 B')
  page.locator('.cost-value-input').nth(1).fill('0.33')
  page.locator('.cost-value-input').nth(1).press('Tab')
  page.locator('.cost-list-price-input').nth(1).fill('0.95')
  page.locator('.cost-list-price-input').nth(1).press('Tab')
  page.locator('#saveBtn').click()
  page.wait_for_function('document.querySelector("#saveState").dataset.status==="manual"')
  page.screenshot(path=str(OUT/f'cost_{width}.png'))
  # switch tab, render price grid with sample product if possible
  page.locator('[data-nav="pricing"]').first.click() if width>1200 else page.locator('[data-view="pricing"]').first.click()
  page.screenshot(path=str(OUT/f'pricing_{width}.png'))
  print(width, 'save-label',page.locator('#saveState').inner_text(),'saveVisible',page.locator('#saveState').is_visible())
  if width==1440:
    page.evaluate('document.querySelector("#authGate").hidden=false')
    page.screenshot(path=str(OUT/'login_1440.png'))
  browser.close()
print('Saved screenshots in',OUT)
