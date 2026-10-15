"""Optional browser regression: python tests/sticky_header_regression.py (requires Playwright)."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
STATE = {
    "version": 4, "currentProjectId": "p1", "projects": [{
        "id": "p1", "name": "回归项目", "currentPackageId": "pkg1",
        "costItems": [
            {"id": f"c{i}", "name": f"测试产品{i}", "type": "product",
             "spec": "", "cost": "1", "listPrice": "2", "active": True, "components": []}
            for i in range(45)
        ],
        "packages": [{"id": "pkg1", "name": "套餐1",
            "products": [{"id": f"r{i}", "costItemId": f"c{i}", "qty": "2"} for i in range(45)],
            "discounts": [{"id": f"d{i}", "zhe": f"{i+6}"} for i in range(3)],
            "fees": []}]
    }]
}

async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                                                   args=["--no-sandbox", "--disable-extensions"])
        for width in (1800, 1024):
            page = await browser.new_page(viewport={"width": width, "height": 900})
            html = (ROOT / "index.html").read_text().replace(
                '<script defer="" src="./app.js"></script>', "")
            await page.set_content(html)
            await page.add_style_tag(content=(ROOT / "styles.css").read_text()
                                     + "\\n" + (ROOT / "v8.css").read_text())
            await page.add_script_tag(content="window.TEST_STATE=" +
                                      json.dumps(STATE, ensure_ascii=False) +
                                      """;window.fetch=async (url)=> {
                                        const wrap=(d)=>new Response(JSON.stringify(d),{
                                         status:200,headers:{'content-type':'application/json'}});
                                        if(url==='/api/me') return wrap({ok:true,user:{
                                          username:'admin01',displayName:'炮台'}});
                                        if(url.startsWith('/api/state')) return wrap({
                                          ok:true,revision:1,owner:'admin01',state:window.TEST_STATE});
                                        return wrap({ok:true});
                                      }""")
            await page.add_script_tag(content=(ROOT / "app.js").read_text())
            await page.locator("#authLoading").wait_for(state="hidden")
            for view, selector in (
                ("cost", "#costView .cost-manager .table-scroll"),
                ("pricing", "#pricingView .products-block .table-scroll"),
            ):
                if view == "pricing":
                    nav = (".nav-item[data-nav=pricing]" if width > 1200
                           else ".mobile-view-tab[data-view=pricing]")
                    await page.locator(nav).click()
                await page.evaluate("window.scrollTo(0,150)")
                before = await page.locator(selector).evaluate(
                    """el=>({clip:getComputedStyle(el).contain,
                             scrollHeight:el.scrollHeight,clientHeight:el.clientHeight})""")
                assert before["clip"] == "paint"
                assert before["scrollHeight"] > before["clientHeight"]
                await page.locator(selector).evaluate("el=>el.scrollTop=500")
                result = await page.locator(selector).evaluate(
                    """el=>({scrollTop:el.scrollTop,boxTop:el.getBoundingClientRect().top,
                         headerTop:el.querySelector('th').getBoundingClientRect().top})""")
                assert result["scrollTop"] > 0
                assert abs(result["boxTop"] - result["headerTop"]) < 2
                print(width, view, "OK")
            await page.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
