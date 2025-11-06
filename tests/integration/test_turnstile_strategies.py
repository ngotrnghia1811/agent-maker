#!/usr/bin/env python3
"""Test various strategies for passing Cloudflare Turnstile in headless mode."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def try_turnstile_click():
    """Strategy: Click the Turnstile checkbox after stealth setup."""
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

    print("=== Strategy: Turnstile checkbox click ===")
    print("Navigating to claude.ai/new ...")
    await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    title = await page.title()
    url = page.url
    print(f"URL: {url}")
    print(f"Title: {title}")

    if "Just a moment" not in title and "challenge" not in url:
        print("No Cloudflare challenge! Page loaded directly.")
        await page.screenshot(path="storage/headless_strat_nochallenge.png")
        await browser.close()
        await pw.stop()
        return True

    print("Cloudflare challenge detected. Attempting Turnstile click...")

    # Look for Turnstile iframe
    turnstile_frame = None
    for frame in page.frames:
        if "challenges.cloudflare.com" in frame.url or "turnstile" in frame.url:
            turnstile_frame = frame
            print(f"  Found Turnstile frame: {frame.url[:100]}")
            break

    if turnstile_frame:
        # Try clicking the checkbox inside the iframe
        try:
            checkbox = turnstile_frame.locator("input[type='checkbox']")
            if await checkbox.count() > 0:
                print("  Found checkbox, clicking...")
                await checkbox.click()
                await page.wait_for_timeout(5000)
            else:
                # Try clicking the label/container
                print("  No checkbox found, trying label click...")
                label = turnstile_frame.locator("label, .cb-i, [class*='check']").first
                if await label.count() > 0:
                    await label.click()
                    await page.wait_for_timeout(5000)
                else:
                    # Try clicking at known coordinates within the frame
                    print("  No label found, trying coordinate click on iframe...")
                    iframe_el = page.locator("iframe[src*='challenges.cloudflare.com']").first
                    box = await iframe_el.bounding_box()
                    if box:
                        # Turnstile checkbox is typically at left-center of the widget
                        click_x = box["x"] + 25
                        click_y = box["y"] + box["height"] / 2
                        print(f"  Clicking at ({click_x}, {click_y})...")
                        await page.mouse.click(click_x, click_y)
                        await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  Turnstile click error: {e}")
    else:
        print("  No Turnstile iframe found. Trying to click the widget area...")
        # The verification widget is typically a specific div
        widget = page.locator("#cf-turnstile-widget, [class*='turnstile'], .cf-challenge-widget").first
        try:
            if await widget.count() > 0:
                await widget.click()
                await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  Widget click error: {e}")

    # Check if challenge cleared
    await page.wait_for_timeout(3000)
    title = await page.title()
    url = page.url
    print(f"\nAfter click:")
    print(f"  URL: {url}")
    print(f"  Title: {title}")

    # Try waiting for navigation
    try:
        await page.wait_for_function(
            """() => !document.title.includes('Just a moment')""",
            timeout=15000,
        )
        print("  Challenge resolved!")
        success = True
    except Exception:
        print("  Challenge NOT resolved after click + wait.")
        success = False

    await page.screenshot(path="storage/headless_strat_turnstile.png")
    print(f"Screenshot saved: storage/headless_strat_turnstile.png")

    await browser.close()
    await pw.stop()
    return success


async def main():
    result = await try_turnstile_click()
    print(f"\n{'SUCCESS' if result else 'FAILED'}")


asyncio.run(main())
