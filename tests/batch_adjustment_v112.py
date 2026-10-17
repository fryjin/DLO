"""Round-trip V1.0.12 TSV, legacy 7-col paste and read-only permissions."""
import importlib.util
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('combo_test', ROOT/'tests/combo_adjustment_v112.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=m.state
blank={"version":4,"currentProjectId":"project-1","projects":[{
 "id":"project-1","name":"测试项目","currentPackageId":"package-1","costItems":[],
 "packages":[{"id":"package-1","name":"套餐1","products":[],"discounts":[{"id":"d1","zhe":"6"}],"fees":[]}]}]}

def page_for(browser, state, owner='admin01'):
  page=browser.new_page(viewport={'width':1600,'height':850})
  raw=(ROOT/'index.html').read_text().replace('<script defer="" src="./app.js"></script>','')
  page.set_content(raw)
  page.add_style_tag(content=(ROOT/'styles.css').read_text()+'\n'+(ROOT/'v8.css').read_text())
  data=json.dumps(state,ensure_ascii=False)
  page.add_script_tag(content='''window.__initial='''+data+''';
    window.fetch=async(url,opts={})=>{
      const ok=(d)=>new Response(JSON.stringify(d),{status:200,headers:{'content-type':'application/json'}});
      if(url==='/api/me')return ok({ok:true,user:{username:'admin01',displayName:'炮台'}});
      if(url.startsWith('/api/state')){
        const target=new URL(url,'https://example.com').searchParams.get('owner')||'admin01';
        return ok({ok:true,owner:target,editable:target==='admin01',state:window.__initial,revision:2});
      }
      return ok({ok:true});
    };''')
  page.add_script_tag(content=(ROOT/'app.js').read_text())
  page.locator('#authLoading').wait_for(state='hidden')
  return page

with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-extensions'])
  page=page_for(browser,state)
  page.locator('#batchCostBtn').click()
  page.locator('#copyBatchBtn').click()
  tsv=page.locator('#batchText').input_value()
  rows=[x.split('\t') for x in tsv.split('\n')]
  assert len(rows[0])==8 and rows[0][5]=='单价调整值',rows[0]
  assert rows[3][5]=='-0.05', rows[3]
  assert rows[5][5]=='+0.10', rows[5]
  page.close()
  other=page_for(browser,blank)
  other.locator('#batchCostBtn').click()
  other.locator('#batchText').fill(tsv)
  other.locator('#applyBatchBtn').click()
  assert other.locator('#batchModal').is_hidden(),other.locator('#batchError').inner_text()
  assert other.locator('#costBody tr.catalog-row').count()==5
  assert other.locator('.cost-price-adjustment-input').first.input_value()=='-0.05'
  assert other.locator('#costBody tr.catalog-row').nth(2).locator('td').nth(7).inner_text().strip()=='¥0.45'
  other.close()
  # Old 7-column text must retain default delta of zero.
  legacy_tsv='\n'.join(['产品品类\t成份\t成份数量\t规格/备注\t单个成本\t单品标价\t状态',
    '普通A\t/\t/\t\t0.1\t0.50\t启用',
    '旧版组合\t普通A\t2\t\t0.2\t1.00\t启用'])
  old=page_for(browser,blank)
  old.locator('#batchCostBtn').click()
  old.locator('#batchText').fill(legacy_tsv)
  old.locator('#applyBatchBtn').click()
  assert old.locator('#batchModal').is_hidden(),old.locator('#batchError').inner_text()
  assert old.locator('.cost-price-adjustment-input').first.input_value()=='0'
  assert old.locator('#costBody tr.catalog-row').nth(1).locator('td').nth(7).inner_text().strip()=='¥1.00'
  old.close()
  readonly=page_for(browser,state)
  readonly.locator('#viewOwnerSelect').select_option('admin02')
  readonly.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin02" && !document.querySelector("#spaceBusy").hidden') if False else None
  readonly.wait_for_function('document.querySelector("#viewOwnerSelect").value==="admin02" && document.querySelector("#spaceBusy").hidden')
  assert readonly.locator('.cost-price-adjustment-input').first.is_disabled(), 'new adjustment input must be disabled in others space'
  assert readonly.locator('#saveBtn').is_hidden()
  readonly.close()
  browser.close()
  print('PASS V1.0.12 TSV: 8-column roundtrip, 7-column backward compatibility, read-only adjustment')
