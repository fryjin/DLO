"""V1.0.5 outer-scroll sticky offset regression, including 125% zoom-equivalent viewport.
Run: python tests/sticky_offsets_regression.py
"""
from pathlib import Path
import asyncio
import json
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
STATE = {"version":4,"currentProjectId":"p1","projects":[{
    "id":"p1","name":"项目1","currentPackageId":"pkg1",
    "costItems":[{"id":f"c{i}","name":f"产品{i}","type":"product","spec":"", "cost":"0.10", "listPrice":"0.20", "active":True, "components":[]} for i in range(28)],
    "packages":[{"id":"pkg1","name":"套餐1", "products":[{"id":f"r{i}","costItemId":f"c{i}","qty":"2"} for i in range(28)], "discounts":[{"id":"d1","zhe":"6"},{"id":"d2","zhe":"6.5"},{"id":"d3","zhe":"7"}],"fees":[]}]
}]}

async def verify():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox','--disable-extensions'])
        scenarios=[(1817,830,1),(1454,664,1.25),(1024,768,1),(900,750,1)]
        for width,height,scale in scenarios:
            page=await browser.new_page(viewport={'width':width,'height':height},device_scale_factor=scale)
            raw=(ROOT/'index.html').read_text(encoding='utf-8').replace('<script defer="" src="./app.js"></script>','')
            await page.set_content(raw)
            await page.add_style_tag(content=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text())
            data=json.dumps(STATE,ensure_ascii=False)
            await page.add_script_tag(content="""window.fetch=async(url,options={})=>{const wrap=d=>new Response(JSON.stringify(d),{status:200,headers:{'content-type':'application/json'}}); if(url==='/api/me')return wrap({ok:true,user:{username:'admin01',displayName:'炮台'}});if(url.startsWith('/api/state'))return wrap({ok:true,revision:1,owner:'admin01',state:"""+data+"""});return wrap({ok:true});};""")
            await page.add_script_tag(content=(ROOT/'app.js').read_text())
            await page.locator('#authLoading').wait_for(state='hidden')
            for view in ('cost','pricing'):
                if view=='pricing':
                    if width<=1200: await page.locator('.mobile-view-tab[data-view="pricing"]').click()
                    else: await page.locator('.nav-item[data-nav="pricing"]').click()
                await page.wait_for_timeout(80)
                for scroll in (0, 125, 180, 260, 450):
                    await page.evaluate(f'window.scrollTo(0,{scroll})')
                    await page.wait_for_timeout(45)
                    d=await page.evaluate("""(view)=> {
                      const top=document.querySelector('.topbar'),head=document.querySelector('.page-head'),bar=document.querySelector('#'+view+'View > .toolbar');
                      const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}};
                      const h=rect(head),b=rect(bar),t=rect(top); return {scrollY:window.scrollY,head:h,toolbar:b,topbar:t,cssHead:getComputedStyle(document.documentElement).getPropertyValue('--subhead-h'),cssTop:getComputedStyle(document.documentElement).getPropertyValue('--top-h')};
                    }""",view)
                    assert d['toolbar']['top'] >= d['head']['bottom']-1.2, f'Overlapping sticky bars at {width}px {view} scroll={scroll}: {d}'
                    if scroll in (180,260):
                        assert abs(d['head']['bottom']-d['toolbar']['top'])<1.2, f'Sticky gap at {width}px {view} scroll={scroll}: {d}'
                    assert abs(d['topbar']['bottom']-d['head']['top'])<1.2, f'Topbar gap at {width}px {view} scroll={scroll}: {d}'
                table='#costView .cost-manager .table-scroll' if view=='cost' else '#pricingView .products-block .table-scroll'
                metrics=await page.locator(table).evaluate("""e=>({scrollHeight:e.scrollHeight,clientHeight:e.clientHeight})""")
                assert metrics['scrollHeight']>metrics['clientHeight'],f'Table not independently scrollable {width} {view} {metrics}'
                await page.locator(table).evaluate('e=>e.scrollTop=450')
                metrics=await page.locator(table).evaluate("""e=>({scrollTop:e.scrollTop,theadY:e.querySelector('th').getBoundingClientRect().top,boxY:e.getBoundingClientRect().top})""")
                assert metrics['scrollTop']>0 and abs(metrics['theadY']-metrics['boxY'])<2, f'Table sticky heading broken {width} {view} {metrics}'
            await page.close()
            print(f'PASS {width}px / DPR {scale}: no sticky gap in both tabs; internal table headers stay sticky')
        await browser.close()

if __name__=='__main__': asyncio.run(verify())
