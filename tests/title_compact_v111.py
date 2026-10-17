"""Verify compact one-row breadcrumb and sticky offsets, independent of production data.
Run: python tests/title_compact_v111.py
"""
from pathlib import Path
import asyncio,json
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent
STATE={"version":4,"currentProjectId":"p1","projects":[{"id":"p1","name":"高地花语","currentPackageId":"k1","costItems":[{"id":"c1","name":"吊牌","type":"product","cost":"0.1","listPrice":"0.25","spec":"100x50","active":True,"components":[]}],"packages":[{"id":"k1","name":"大食量","products":[{"id":"r1","costItemId":"c1","qty":"2"}],"fees":[],"discounts":[{"id":"d1","zhe":"6"},{"id":"d2","zhe":"6.5"},{"id":"d3","zhe":"7"}]}]}]}

async def run():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-extensions'])
  for width,height in [(1817,900),(1440,900),(1024,768),(900,750)]:
   page=await browser.new_page(viewport={'width':width,'height':height})
   raw=(ROOT/'index.html').read_text(encoding='utf-8').replace('<script defer="" src="./app.js"></script>','')
   await page.set_content(raw)
   await page.add_style_tag(content=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text())
   data=json.dumps(STATE,ensure_ascii=False)
   await page.add_script_tag(content="""window.fetch=async(url,options={})=>{const wrap=d=>new Response(JSON.stringify(d),{status:200,headers:{'content-type':'application/json'}});if(url==='/api/me')return wrap({ok:true,user:{username:'admin01',displayName:'炮台'}});if(url.startsWith('/api/state'))return wrap({ok:true,revision:1,owner:'admin01',state:"""+data+"""});return wrap({ok:true});};""")
   await page.add_script_tag(content=(ROOT/'app.js').read_text())
   await page.locator('#authLoading').wait_for(state='hidden')
   for view,title in [('cost','工作台/产品信息管理'),('pricing','工作台/套餐售价计算')]:
    if view=='pricing':
     nav=f'.nav-item[data-nav="pricing"]' if width>1200 else '.mobile-view-tab[data-view="pricing"]'
     await page.locator(nav).click()
    metrics=await page.evaluate('''(view)=>{
      const head=document.querySelector('.page-head'), heading=document.querySelector('.page-heading');
      const bar=document.querySelector('#'+view+'View>.toolbar');
      const r=x=>{const v=x.getBoundingClientRect();return {top:v.top,bottom:v.bottom,height:v.height}};
      return {head:r(head),heading:r(heading),bar:r(bar),cssH:getComputedStyle(document.documentElement).getPropertyValue('--subhead-h'),text:heading.innerText.replace(/\\s/g,''),scrollWidth:heading.scrollWidth,clientWidth:heading.clientWidth};
    }''',view)
    assert metrics['text']==title,(width,view,metrics)
    expected=56 if width>1600 else 50 if width>1200 else 48
    assert abs(metrics['head']['height']-expected)<1,(width,view,metrics)
    assert metrics['bar']['top']>=metrics['head']['bottom']-1.5,(width,view,metrics)
    assert metrics['heading']['height']<30,(width,view,metrics)
    assert abs(metrics['heading']['top']-metrics['head']['top'])<expected,(width,view,metrics)
    assert metrics['scrollWidth']<=metrics['clientWidth']+1,(width,view,metrics)
    await page.evaluate('window.scrollTo(0,200)')
    await page.wait_for_timeout(70)
    metrics=await page.evaluate('''(view)=>{const h=document.querySelector('.page-head').getBoundingClientRect();const b=document.querySelector('#'+view+'View>.toolbar').getBoundingClientRect();return [h.bottom,b.top]}''',view)
    assert abs(metrics[0]-metrics[1])<=1.5,(width,view,metrics)
    await page.evaluate('window.scrollTo(0,0)')
    if width==1440:
     await page.screenshot(path='/mnt/data/dopamine_v111_'+view+'_preview.png')
   print(f'PASS {width}px: one-line titles, compact header, sticky toolbar gap 0')
   await page.close()
  await browser.close()
if __name__=='__main__':asyncio.run(run())
