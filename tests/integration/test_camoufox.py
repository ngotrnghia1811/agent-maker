#!/usr/bin/env python3
"""Test Camoufox headless mode against Claude's Cloudflare Turnstile."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))


async def test_camoufox_headless():
    from camoufox.async_api import AsyncCamoufox

    print("=== Camoufox Headless Test ===")

    # Load cookies from storage state to inject
    state_path = Path("storage/claude_storage_state.json")
    storage_state = json.loads(state_path.read_text()) if state_path.exists() else None

    async with AsyncCamoufox(headless=True, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )

        # Inject cookies from storage state
        if storage_state and storage_state.get("cookies"):
            await ctx.add_cookies(storage_state["cookies"])
            print(f"  Injected {len(storage_state['cookies'])} cookies from storage state")

        page = await ctx.new_page()

        print("Navigating to claude.ai/new ...")
        resp = await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=30000)
        print(f"HTTP status: {resp.status if resp else 'no response'}")

        # Wait a bit for any challenge
        await page.wait_for_timeout(5000)

        title = await page.title()
        url = page.url
        body = await page.evaluate("document.body?.innerText?.substring(0, 500) || ''")
        print(f"URL: {url}")
        print(f"Title: {title}")
        print(f"Body: {body[:300]}")

        if "Just a moment" in title or "challenge" in url:
            print("\nCloudflare challenge detected. Waiting up to 30s for auto-resolve...")
            try:
                await page.wait_for_function(
                    """() => !document.title.includes('Just a moment')""",
                    timeout=30000,
                )
                title = await page.title()
                url = page.url
                print(f"  Resolved! URL: {url}")
                print(f"  Title: {title}")
            except Exception:
                print("  Challenge did NOT auto-resolve.")

                # Try clicking the Turnstile
                print("  Trying to click Turnstile...")
                for frame in page.frames:
                    if "challenges.cloudflare.com" in frame.url:
                        print(f"  Found frame: {frame.url[:80]}")
                        try:
                            # Try clicking inside the frame
                            await frame.click("body", timeout=5000)
                            await page.wait_for_timeout(5000)
                        except Exception as e:
                            print(f"  Frame click failed: {e}")

                title = await page.title()
                url = page.url
                print(f"  After click - URL: {url}")
                print(f"  After click - Title: {title}")

        # Check for chat input
        success = False
        for sel in [
            'div.ProseMirror[contenteditable="true"]',
            '[data-testid="chat-input"]',
            'div[contenteditable="true"]',
        ]:
            try:
                vis = await page.locator(sel).first.is_visible(timeout=2000)
                if vis:
                    print(f"\n  Chat input found: {sel}")
                    success = True
                    break
            except Exception:
                continue

        await page.screenshot(path="storage/camoufox_headless.png")
        print(f"\nScreenshot: storage/camoufox_headless.png")
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")

    return success


async def main():
    result = await test_camoufox_headless()
    sys.exit(0 if result else 1)


asyncio.run(main())
