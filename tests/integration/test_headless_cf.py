"""Test headless mode with Cloudflare bypass using stealth."""
import asyncio
from playwright.async_api import async_playwright


async def test():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--headless=new",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    ctx = await browser.new_context(
        storage_state="storage/claude_storage_state.json",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        if (!window.chrome) { window.chrome = { runtime: {} }; }
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """)
    page = await ctx.new_page()

    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
        print("playwright-stealth applied")
    except ImportError:
        print("playwright-stealth not available")

    await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=60000)

    for i in range(15):
        title = await page.title()
        body = await page.evaluate("document.body?.innerText?.substring(0, 200) || ''")
        print(f"  [{i}] title={title[:50]}")
        if "security" not in body.lower() and "moment" not in title.lower() and "verif" not in body.lower():
            break
        await page.wait_for_timeout(3000)

    print(f"Final: title={await page.title()}, url={page.url}")
    body = await page.evaluate("document.body?.innerText?.substring(0, 300) || ''")
    print(f"Body: {body[:200]}")

    btn = page.locator('[data-testid="model-selector-dropdown"]').first
    if await btn.count() > 0:
        print(f"Model selector: {await btn.inner_text()}")
    else:
        print("Model selector NOT found by testid")

    # Search for buttons with model-related text
    all_btns = await page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('button').forEach(b => {
            const text = b.innerText?.trim();
            const testid = b.getAttribute('data-testid') || '';
            if (text && (text.includes('Sonnet') || text.includes('Opus') || text.includes('Haiku') || testid.includes('model'))) {
                results.push({text: text.substring(0, 80), testid, tag: b.tagName});
            }
        });
        return results;
    }""")
    print(f"Model buttons: {all_btns}")

    # Also list all data-testid attributes
    testids = await page.evaluate("""() => {
        const ids = [];
        document.querySelectorAll('[data-testid]').forEach(el => {
            ids.push(el.getAttribute('data-testid'));
        });
        return ids;
    }""")
    print(f"All testids: {testids}")

    await browser.close()
    await pw.stop()


asyncio.run(test())
