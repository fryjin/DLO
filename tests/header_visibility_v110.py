"""Regression for the actual V1.0.9 'vanishing header' user screenshots.
Run: python tests/header_visibility_v110.py (playwright + system Chromium).
Covers nested scroll, outer-page scroll, and horizontal scroll together.
"""
from pathlib import Path
import asyncio
import json
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parent.parent
STATE={"version":4,"currentProjectId":"p1","projects":[{
  "id":"p1","name":"高地花语","currentPackageId":"pkg1",
  "costItems":[{"id":f"c{i}","name":f"纸品{i+1}","type":"product","spec":"100*50","cost":"0.10","listPrice":"0.25","active":True,"components":[]} for i in range(35)],
  "packages":[{"id":"pkg1","name":"大食量","products":[{"id":f"r{i}","costItemId":f"c{i}","qty":"2"} for i in range(35)],"fees":[],"discounts":[{"id":"d1","zhe":"6"},{"id":"d2","zhe":"6.5"},{"id":"d3","zhe":"7"}]}]
}]}

async def run():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-extensions'])
        for width,height in [(1817,830),(1440,900),(1024,768)]:
            page=await browser.new_page(viewport={'width':width,'height':height})
            raw=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
            await page.set_content(raw)
            await page.add_style_tag(content=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text())
            state=json.dumps(STATE,ensure_ascii=False)
            await page.add_script_tag(content="""window.fetch=async(url,options={})=>{const wrap=d=>new Response(JSON.stringify(d),{status:200,headers:{'content-type':'application/json'}}); if(url==='/api/me')return wrap({ok:true,user:{username:'admin01',displayName:'炮台'}});if(url.startsWith('/api/state'))return wrap({ok:true,revision:1,owner:'admin01',state:"""+state+"""});return wrap({ok:true});};""")
            await page.add_script_tag(content=(ROOT/'app.js').read_text())
            await page.locator('#authLoading').wait_for(state='hidden')
            # Need extra outer-scroll room to reproduce heading disappearance in the summary.
            await page.evaluate("document.querySelector('main').style.paddingBottom='800px'")
            cost='#costView .cost-manager .table-scroll'
            prod='#pricingView .products-block .table-scroll'
            summary='#pricingView .summary-block .summary-scroll'
            await page.locator(cost).evaluate('e=>e.scrollTop=530')
            await page.wait_for_timeout(70)
            assert await page.locator('.floating-table-head').is_hidden(),'do not duplicate a naturally visible table heading'
            await page.evaluate('window.scrollTo(0,430)')
            await page.wait_for_timeout(80)
            assert await page.locator('.floating-table-head').is_visible(),'cost header should remain visible when outer scroll clips original'
            assert await page.locator('.floating-table-head thead th').first.text_content()=='排序'
            await page.evaluate('window.scrollTo(0,0)')
            await page.wait_for_timeout(80)
            assert await page.locator('.floating-table-head').is_hidden()

            nav='.nav-item[data-nav="pricing"]' if width>1200 else '.mobile-view-tab[data-view="pricing"]'
            await page.locator(nav).click()
            await page.locator(prod).evaluate('e=>e.scrollTop=530')
            await page.wait_for_timeout(70)
            firstrow=await page.locator('#productHead tr:first-child').evaluate('e=>e.getBoundingClientRect().height')
            secondtop=await page.locator('#productHead tr:nth-child(2) th').first.evaluate('e=>getComputedStyle(e).top')
            assert abs(float(secondtop[:-2])-firstrow)<1.5, (firstrow,secondtop)
            assert await page.locator('.floating-table-head').is_hidden()
            await page.evaluate('window.scrollTo(0,550)')
            await page.wait_for_timeout(90)
            header=page.locator('.floating-table-head')
            assert await header.is_visible(),'pricing source header went under sticky toolbar, but the duplicate was not shown'
            txt=await header.inner_text()
            assert all(label in txt for label in ['排序','产品品类','标价小计','6\n折','6.5\n折','7\n折']),txt
            # Compare first two column coordinates in actual body and floating header.
            d=await page.evaluate('''()=>{
              const body=[...document.querySelector('#productBody tr').cells].map(x=>x.getBoundingClientRect().left);
              const floating=[...document.querySelector('.floating-table-head thead tr').cells].slice(0,7).map(x=>x.getBoundingClientRect().left);
              return {body,floating};
            }''')
            assert all(abs(a-b)<2 for a,b in zip(d['body'],d['floating'])),d
            await page.locator(prod).evaluate('e=>e.scrollLeft=280')
            await page.wait_for_timeout(90)
            off=await page.evaluate('''()=>({source:document.querySelector('#productScroll').scrollLeft, floating:document.querySelector('.floating-table-head').scrollLeft})''')
            assert abs(off['source']-off['floating'])<=1,off
            # Floating sticky left columns stay aligned to actual sticky left data cells.
            dd=await page.evaluate('''()=>{
              const th=document.querySelector('.floating-table-head thead .s1');
              const td=document.querySelector('#productBody tr .s1');
              return [th.getBoundingClientRect().left,td.getBoundingClientRect().left];
            }''')
            assert abs(dd[0]-dd[1])<2,dd
            await page.locator(prod).evaluate('e=>e.scrollLeft=0')
            if width==1817:
                await page.screenshot(path=str(ROOT/'tests'/'v110_products_fixed.png'))
            # Actual summary screenshot: table-header row is obscured by the
            # sticky toolbar after the *outer* document scrolls past it.
            target=await page.locator(summary).evaluate('e=>e.getBoundingClientRect().top+window.scrollY')
            toolbarBottom=await page.locator('#pricingView>.toolbar').evaluate('e=>e.getBoundingClientRect().bottom')
            await page.evaluate('y=>window.scrollTo(0,y)',target-toolbarBottom+95)
            await page.wait_for_timeout(90)
            assert await header.is_visible(),f'summary header not visible at width {width}'
            text=await header.inner_text()
            assert '折扣方案' in text and '原价' in text and '6.5折' in text, text
            if width==1817:
                await page.screenshot(path=str(ROOT/'tests'/'v110_summary_fixed.png'))
            print(f'PASS {width}px: product, pricing, and summary headers remain visible across independent/outer/horizontal scrolling')
            await page.close()
        await browser.close()

if __name__=='__main__':asyncio.run(run())
