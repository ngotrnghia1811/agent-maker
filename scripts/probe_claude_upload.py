#!/usr/bin/env python3
"""Probe Claude.ai file upload UI elements."""
import asyncio
import sys
sys.path.insert(0, "src")

from universal_agents.browser.browser_manager import BrowserManager
from universal_agents.core.config import BrowserConfig


async def main():
    config = BrowserConfig(
        headless=False,
        base_url="https://claude.ai/new",
        storage_state="storage/claude_storage_state.json",
    )
    mgr = BrowserManager(config)
    page = await mgr.ensure_page()
    await page.goto("https://claude.ai/new")
    await page.wait_for_load_state("networkidle", timeout=30_000)
    print(f"Page URL: {page.url}")

    # Check file upload related elements
    upload_selectors = [
        ('Add files button', 'button[aria-label*="Add files"]'),
        ('Attach button', 'button[aria-label*="Attach"]'),
        ('Upload button', 'button[aria-label*="Upload"]'),
        ('Add content', '[aria-label*="Add content"]'),
        ('Add file button', 'button[aria-label*="Add file"]'),
        ('attach testid', 'button[data-testid*="attach"]'),
        ('upload testid', 'button[data-testid*="upload"]'),
        ('file-upload input', 'input[data-testid="file-upload"]'),
        ('file input onpage', '#chat-input-file-upload-onpage'),
        ('any file input', 'input[type="file"]'),
        ('pdf input', 'input[accept*="pdf"]'),
    ]

    for name, sel in upload_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count > 0:
                for i in range(count):
                    el = loc.nth(i)
                    visible = await el.is_visible()
                    aria = await el.get_attribute("aria-label") or ""
                    testid = await el.get_attribute("data-testid") or ""
                    tag = await el.evaluate("e => e.tagName")
                    print(f"  ✅ {name}: tag={tag} visible={visible} aria='{aria}' testid='{testid}'")
            else:
                print(f"  ❌ {name}: not found")
        except Exception as e:
            print(f"  ❌ {name}: error - {e}")

    # Also look at all buttons in the input area
    print("\nAll buttons near input area:")
    buttons = page.locator("fieldset button, form button, [class*='input'] button, [class*='chat'] button")
    count = await buttons.count()
    for i in range(min(count, 20)):
        btn = buttons.nth(i)
        try:
            aria = await btn.get_attribute("aria-label") or ""
            testid = await btn.get_attribute("data-testid") or ""
            text = (await btn.text_content() or "").strip()[:50]
            visible = await btn.is_visible()
            if visible:
                print(f"  Button[{i}]: aria='{aria}' testid='{testid}' text='{text}'")
        except:
            pass

    input("Press Enter to close browser...")
    await mgr.close()


asyncio.run(main())
