#!/usr/bin/env python3
"""Capture Gemini storage state by logging into Google in a visible browser.

Usage:
    python tests/integration/capture_gemini_auth.py

Opens a visible browser window pointing to gemini.google.com.
Log in with your Google account manually, then press Enter in the terminal.
Cookies are saved to storage/gemini_storage_state.json.
"""

import asyncio
import json
from pathlib import Path

async def capture():
    from camoufox.async_api import AsyncCamoufox

    print("Launching visible browser for Google login...")
    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()
        await page.goto("https://gemini.google.com")

        print("\n" + "=" * 60)
        print("  Log in to your Google account in the browser window.")
        print("  Once you see the Gemini chat page, come back here")
        print("  and press Enter to save your session cookies.")
        print("=" * 60)

        input("\nPress Enter after logging in...")

        # Capture cookies
        cookies = await ctx.cookies()
        state = {"cookies": cookies}

        out = Path("storage/gemini_storage_state.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"\nSaved {len(cookies)} cookies to {out}")

        # Verify
        title = await page.title()
        url = page.url
        print(f"Page title: {title}")
        print(f"Page URL: {url}")

if __name__ == "__main__":
    asyncio.run(capture())
