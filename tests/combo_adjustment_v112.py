"""Cloud Lite V1.0.12: signed combo-unit adjustment, nested pricing, table layout,
JSON persistence, batch clipboard, owner-only edits, and visual regression.
Run: python tests/combo_adjustment_v112.py
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
longname='超长组成：印刷折页与双面卡片及透明包装袋特别定制加长规格，纸品、包装辅料、贴纸多件组合'
state={"version":4,"currentProjectId":"project-1","projects":[{
  "id":"project-1","name":"测试项目","currentPackageId":"package-1",
  "costItems":[
    {"id":"a","name":longname,"type":"product","spec":"","cost":"0.05","listPrice":"0.15","active":True,"components":[]},
    {"id":"b","name":"品B","type":"product","spec":"","cost":"0.08","listPrice":"0.20","active":True,"components":[]},
    {"id":"combo-1","name":"一级组合","type":"combo","spec":"","cost":"0","listPrice":"0","priceAdjustment":"-0.05","active":True,
     "components":[{"id":"ca","costItemId":"a","qty":"2"},{"id":"cb","costItemId":"b","qty":"1"}]},
    {"id":"combo-2","name":"二级组合","type":"combo","spec":"","cost":"0","listPrice":"0","priceAdjustment":"+0.10","active":True,
     "components":[{"id":"cc","costItemId":"combo-1","qty":"2"}]},
    {"id":"combo-3","name":"长成份组合","type":"combo","spec":"","cost":"0","listPrice":"0","priceAdjustment":"0","active":True,
     "components":[{"id":"ce","costItemId":"a","qty":"3"}]}
  ],"packages":[{"id":"package-1","name":"套餐1","products":[{"id":"row-1","costItemId":"combo-2","qty":"3"}],
      "discounts":[{"id":"d1","zhe":"6"}],"fees":[]}]
}]}

def run():
  with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-extensions'])
    for width in [1817,1440,1024]:
      page=browser.new_page(viewport={'width':width,'height':900})
      errs=[]
      page.on('pageerror',lambda err:errs.append(str(err)))
      html=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
      page.set_content(html)
      page.add_style_tag(content=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text())
      page.add_script_tag(content='''window.__mockState = '''+json.dumps(state,ensure_ascii=False)+''';
        window.__saves=[];
        window.fetch=async(url,options={})=>{
          const respond=(d)=>new Response(JSON.stringify(d),{status:200,headers:{'content-type':'application/json'}});
          if(url==='/api/me')return respond({ok:true,user:{username:'admin01',displayName:'炮台'}});
          if(url==='/api/state'&&options.method==='POST'){
            const state=JSON.parse(options.body).state;window.__mockState=state;window.__saves.push(state);
            return respond({ok:true,revision:window.__saves.length+1,updatedAt:Date.now(),updatedBy:'admin01'});
          }
          if(url.startsWith('/api/state'))return respond({ok:true,owner:'admin01',editable:true,state:window.__mockState,revision:1});
          return respond({ok:true});
        };''')
      page.add_script_tag(content=(ROOT/'app.js').read_text())
      page.locator('#authLoading').wait_for(state='hidden')
      rows=page.locator('#costBody tr.catalog-row')
      assert rows.count()==5, f'{width}: rows missing, errors={errs}'
      assert page.locator('#costBody .cost-price-adjustment-input').count()==3
      assert page.locator('#costBody tr.catalog-row').nth(2).locator('td').nth(7).inner_text().strip()=='¥0.45'
      assert page.locator('#costBody tr.catalog-row').nth(3).locator('td').nth(7).inner_text().strip()=='¥1.00'
      css=page.evaluate('''()=>{const t=document.querySelector('.cost-table');const r=t.getBoundingClientRect();
        const ths=[...t.querySelectorAll('thead th')].map(th=>({text:th.textContent.trim(),width:th.getBoundingClientRect().width}));
        return {tableW:r.width,ths, colCount:t.querySelectorAll('col').length,thCount:t.querySelectorAll('th').length};}''')
      assert css['colCount']==11 and css['thCount']==11, css
      # Columns are deterministic even when the table is wider than the viewport.
      namew=css['ths'][1]['width'];compw=css['ths'][2]['width'];tablew=css['tableW']
      assert .14 < namew/tablew < .19, (width,css)
      assert .15 < compw/tablew < .20, (width,css)
      assert css['ths'][6]['text']=='单价调整值'
      if width==1817:
        # Multi-line ingredient summaries expand a row when a long name is used.
        rowheight=page.locator('#costBody tr.catalog-row').nth(2).evaluate('(el)=>el.getBoundingClientRect().height')
        assert rowheight>43, f'Combo ingredients not wrapping: height={rowheight}'
        page.screenshot(path=str(ROOT/'tests'/'v112_cost_preview.png'),full_page=False)
      # Price adjustment can increase/decrease price and propagate into nested combos.
      inp=page.locator('.cost-price-adjustment-input[data-id="combo-1"]')
      inp.fill('+0.15')
      inp.press('Tab')
      assert page.locator('#costBody tr.catalog-row').nth(2).locator('td').nth(7).inner_text().strip()=='¥0.65'
      assert page.locator('#costBody tr.catalog-row').nth(3).locator('td').nth(7).inner_text().strip()=='¥1.40'
      if width==1817:
        page.locator('.nav-item[data-nav="pricing"]').click()
        assert page.locator('#metricTotalSales').inner_text().strip()=='¥4.20'
        assert page.locator('#productBody tr').first.locator('td').nth(5).inner_text().strip()=='¥4.20'
        page.screenshot(path=str(ROOT/'tests'/'v112_pricing_preview.png'),full_page=False)
        page.locator('.nav-item[data-nav="cost"]').click()
      # Prevent invalid adjustment from persisting.
      inp=page.locator('.cost-price-adjustment-input[data-id="combo-1"]')
      inp.fill('-999')
      inp.press('Tab')
      assert page.locator('.cost-price-adjustment-input[data-id="combo-1"]').input_value()=='+0.15'
      page.locator('#saveBtn').click()
      page.wait_for_function('window.__saves.length===1')
      assert page.evaluate('window.__saves[0].projects[0].costItems[2].priceAdjustment')=='+0.15'
      assert not errs,errs
      page.close()
      print(f'PASS {width}px: price adjustment, nested combo, layout, persistence, validation')
    browser.close()

if __name__=='__main__':run()
