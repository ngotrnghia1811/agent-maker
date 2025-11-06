#!/usr/bin/env python3
"""Debug: Inspect Claude model selector DOM."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = await browser.new_context(
        storage_state="storage/claude_storage_state.json",
        viewport={"width": 1280, "height": 900},
    )
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    page = await ctx.new_page()
    await page.goto("https://claude.ai/new", wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # Find elements with 'model' in attributes
    elements = await page.evaluate("""() => {
        const results = [];
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const attrs = {};
            for (const attr of el.attributes) {
                if (attr.name.includes('model') || attr.value.includes('model') ||
                    attr.name.includes('selector') || attr.value.includes('selector') ||
                    attr.value.includes('sonnet') || attr.value.includes('opus') ||
                    attr.value.includes('claude')) {
                    attrs[attr.name] = attr.value;
                }
            }
            if (Object.keys(attrs).length > 0) {
                results.push({
                    tag: el.tagName,
                    text: el.innerText?.substring(0, 100) || '',
                    attrs: attrs,
                });
            }
        }
        return results;
    }""")

    print(f"\n=== Elements with model/selector/sonnet/opus/claude attributes ({len(elements)}) ===\n")
    for el in elements[:40]:
        print(f"  <{el['tag']}> text='{el['text'][:60]}' attrs={el['attrs']}")

    # Now find and click the model button
    print("\n=== Looking for model button ===")
    # Try various selectors
    selectors = [
        '[data-testid="model-selector-dropdown"]',
        'button:has-text("Sonnet")',
        'button:has-text("Claude")',
        'button:has-text("Opus")',
        '[class*="model"]',
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        cnt = await loc.count()
        if cnt > 0:
            txt = await loc.inner_text()
            print(f"  ✅ {sel} → '{txt[:60]}'")
        else:
            print(f"  ❌ {sel} → not found")

    # Click the model button
    btn = page.locator('button:has-text("Sonnet")').first
    if await btn.count() > 0:
        print("\n=== Clicking model button ===")
        await btn.click()
        await page.wait_for_timeout(2000)

        # Dump all visible popover/dropdown/dialog content
        for sel in ['[role="dialog"]', '[role="listbox"]', '[role="menu"]', '[data-radix-popper-content-wrapper]', '[class*="popover"]', '[class*="dropdown"]', '[class*="modal"]']:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                txt = await loc.inner_text()
                print(f"\n  Found {sel}:")
                print(f"    {txt[:500]}")

        # Also get all buttons/options visible
        visible_buttons = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('button, [role="option"], [role="menuitem"], [role="menuitemradio"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    const text = el.innerText?.trim();
                    if (text && (text.includes('Sonnet') || text.includes('Opus') || text.includes('Haiku') || text.includes('Claude') || text.includes('model'))) {
                        results.push({
                            tag: el.tagName,
                            text: text.substring(0, 100),
                            role: el.getAttribute('role'),
                            testid: el.getAttribute('data-testid'),
                            class: el.className?.substring(0, 80),
                        });
                    }
                }
            });
            return results;
        }""")
        print(f"\n=== Visible model-related buttons ({len(visible_buttons)}) ===")
        for b in visible_buttons[:20]:
            print(f"  <{b['tag']}> role={b['role']} testid={b['testid']} text='{b['text'][:60]}'")

    await page.wait_for_timeout(3000)
    await browser.close()
    await pw.stop()

asyncio.run(main())
