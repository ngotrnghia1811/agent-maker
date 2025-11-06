"""Re-authenticate with Claude to refresh storage state."""
import asyncio
from playwright.async_api import async_playwright


async def reauth():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    ctx = await browser.new_context(
        storage_state="storage/claude_storage_state.json",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    await ctx.add_init_script(
        'Object.defineProperty(navigator, "webdriver", { get: () => undefined });'
    )
    page = await ctx.new_page()
    await page.goto("https://claude.ai/new", wait_until="domcontentloaded")

    print("Browser opened. Pass any Cloudflare challenge and ensure claude.ai loads.")
    print("Press ENTER when ready...")
    await asyncio.get_event_loop().run_in_executor(None, input)

    await ctx.storage_state(path="storage/claude_storage_state.json")
    print(f"Storage state saved! Title: {await page.title()}")

    await browser.close()
    await pw.stop()


asyncio.run(reauth())
