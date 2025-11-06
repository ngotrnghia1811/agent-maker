#!/usr/bin/env python3
"""Probe Claude.ai page to see what's visible after login."""
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
    print("Navigated to claude.ai/new")

    # Wait for page to settle
    await page.wait_for_load_state("networkidle", timeout=30_000)
    print(f"Page URL: {page.url}")
    print(f"Page title: {await page.title()}")

    # Check what's visible
    selectors_to_check = [
        ("ProseMirror input", "div.ProseMirror[contenteditable='true']"),
        ("contenteditable textbox", "div[contenteditable='true'][role='textbox']"),
        ("any contenteditable", "div[contenteditable='true']"),
        ("login button", 'a[href*="login"]'),
        ("sign in button", 'button:has-text("Sign in")'),
        ("log in button", 'button:has-text("Log in")'),
        ("continue button", 'button:has-text("Continue")'),
        ("accept button", 'button:has-text("Accept")'),
        ("start button", 'button:has-text("Start")'),
        ("cookie banner", '[class*="cookie"]'),
        ("consent dialog", '[class*="consent"]'),
        ("modal dialog", '[role="dialog"]'),
        ("send button", 'button[aria-label*="Send"]'),
        ("textarea", "textarea"),
    ]

    for name, sel in selectors_to_check:
        try:
            loc = page.locator(sel).first
            count = await loc.count()
            if count > 0:
                visible = await loc.is_visible()
                text = ""
                try:
                    text = (await loc.text_content() or "")[:100]
                except:
                    pass
                print(f"  ✅ {name}: found (visible={visible}) text='{text}'")
            else:
                print(f"  ❌ {name}: not found")
        except Exception as e:
            print(f"  ❌ {name}: error - {e}")

    # Also get page HTML snippet
    body = await page.query_selector("body")
    if body:
        html = await body.inner_html()
        print(f"\nBody HTML length: {len(html)}")
        # Look for key words
        for word in ["login", "sign in", "ProseMirror", "contenteditable", "consent", "cookie", "error"]:
            if word.lower() in html.lower():
                print(f"  Found '{word}' in HTML")

    input("Press Enter to close browser...")
    await mgr.close()


asyncio.run(main())
