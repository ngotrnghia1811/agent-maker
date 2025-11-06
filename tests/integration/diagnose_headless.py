#!/usr/bin/env python3
"""Diagnose headless mode — what does Claude.ai show?"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def diagnose():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )
    ctx = await browser.new_context(
        storage_state="storage/claude_storage_state.json",
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    stealth = Stealth()
    await stealth.apply_stealth_async(ctx)
    page = await ctx.new_page()

    print("Navigating to claude.ai/new ...")
    resp = await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=30000)
    print(f"HTTP status: {resp.status if resp else 'no response'}")
    await page.wait_for_timeout(5000)

    title = await page.title()
    url = page.url
    body_text = await page.evaluate("document.body?.innerText?.substring(0, 800) || ''")

    print(f"URL: {url}")
    print(f"Title: {title}")
    print(f"Body (first 800 chars):\n{body_text}")
    print()

    # Screenshot
    Path("storage").mkdir(exist_ok=True)
    await page.screenshot(path="storage/headless_diagnose.png", full_page=True)
    print("Screenshot saved to storage/headless_diagnose.png")

    # Check key selectors
    selectors = [
        'div.ProseMirror[contenteditable="true"]',
        '[data-testid="chat-input"]',
        'div[contenteditable="true"]',
        "textarea",
        '#challenge-stage',
        '.cf-browser-verification',
        '[id*="cf-"]',
    ]
    print("\nSelector visibility check:")
    for sel in selectors:
        try:
            vis = await page.locator(sel).first.is_visible(timeout=1000)
            count = await page.locator(sel).count()
            print(f"  {sel}: visible={vis}, count={count}")
        except Exception as e:
            print(f"  {sel}: error ({e})")

    await browser.close()
    await pw.stop()


asyncio.run(diagnose())
