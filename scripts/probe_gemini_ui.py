#!/usr/bin/env python3
"""Probe Gemini page for model picker selectors."""

import asyncio
import json
from pathlib import Path


async def probe():
    from camoufox.async_api import AsyncCamoufox

    state_path = Path("storage/gemini_storage_state.json")
    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900}, locale="en-US"
        )
        state = json.loads(state_path.read_text())
        if state.get("cookies"):
            await ctx.add_cookies(state["cookies"])
        page = await ctx.new_page()
        await page.goto("https://gemini.google.com")
        await page.wait_for_selector(
            'div[contenteditable="true"]', state="visible", timeout=30000
        )
        await asyncio.sleep(3)

        # Try various model picker selectors
        selectors = [
            'button[data-test-id="bard-mode-menu-button"]',
            'button[aria-label*="model"]',
            'button[aria-label*="Model"]',
            '[data-test-id*="mode"]',
            '[data-test-id*="model"]',
            'button[aria-haspopup="listbox"]',
            'button[aria-haspopup="menu"]',
            'button[aria-haspopup="true"]',
        ]
        for sel in selectors:
            count = await page.locator(sel).count()
            if count > 0:
                text = await page.locator(sel).first.inner_text()
                print(f"FOUND: {sel} -> count={count}, text={repr(text.strip())}")
            else:
                print(f"MISS:  {sel}")

        # Dump all buttons with data-test-id
        buttons_with_test_id = await page.evaluate(
            """() => {
            const btns = document.querySelectorAll('button[data-test-id]');
            return Array.from(btns).map(b => ({
                testId: b.getAttribute('data-test-id'),
                text: b.innerText.trim().substring(0, 100),
                ariaLabel: b.getAttribute('aria-label')
            }));
        }"""
        )
        print("\nButtons with data-test-id:")
        for b in buttons_with_test_id:
            print(f"  {b}")

        # Look for model-related elements
        model_els = await page.evaluate(
            """() => {
            const all = document.querySelectorAll('*');
            const results = [];
            for (const el of all) {
                const text = (el.innerText || '').toLowerCase();
                const testId = el.getAttribute('data-test-id') || '';
                if ((text.includes('gemini') && el.tagName === 'BUTTON') ||
                    testId.toLowerCase().includes('model') ||
                    testId.toLowerCase().includes('mode')) {
                    results.push({
                        tag: el.tagName,
                        testId: testId,
                        text: (el.innerText || '').trim().substring(0, 100),
                        ariaLabel: el.getAttribute('aria-label'),
                        role: el.getAttribute('role')
                    });
                }
            }
            return results;
        }"""
        )
        print("\nModel-related elements:")
        for m in model_els:
            print(f"  {m}")

        # Look for anything with "pro" or "flash" or "fast" text in buttons
        keyword_els = await page.evaluate(
            """() => {
            const btns = document.querySelectorAll('button, [role="button"], [role="option"], [role="menuitem"]');
            const results = [];
            for (const el of btns) {
                const text = (el.innerText || '').toLowerCase();
                if (text.includes('pro') || text.includes('flash') || text.includes('fast') ||
                    text.includes('thinking') || text.includes('2.5') || text.includes('2.0')) {
                    results.push({
                        tag: el.tagName,
                        text: (el.innerText || '').trim().substring(0, 120),
                        ariaLabel: el.getAttribute('aria-label'),
                        className: (el.className || '').substring(0, 80),
                        testId: el.getAttribute('data-test-id')
                    });
                }
            }
            return results;
        }"""
        )
        print("\nKeyword elements (pro/flash/fast/thinking):")
        for k in keyword_els:
            print(f"  {k}")

        input("\nPress ENTER to close browser...")
        await browser.close()


asyncio.run(probe())
