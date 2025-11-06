#!/usr/bin/env python3
"""Quick diagnostic: test if Gemini auth works from source."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from universal_agents.providers.gemini.data import GeminiDataAgent
from universal_agents.providers.gemini.config import GeminiDataConfig


async def test():
    config = GeminiDataConfig(
        headless=False,
        storage_state="storage/gemini_storage_state.json",
    )
    agent = GeminiDataAgent(config)
    async with agent:
        page = await agent.browser_mgr.ensure_page()
        await agent.browser_mgr.navigate("https://gemini.google.com")
        await asyncio.sleep(5)

        # Check for sign-in indicator
        sign_in = page.locator('a[href*="accounts.google"]')
        sign_in_count = await sign_in.count()
        print(f"Sign in links: {sign_in_count}")
        if sign_in_count > 0:
            for i in range(sign_in_count):
                el = sign_in.nth(i)
                text = (await el.inner_text()).strip()
                href = await el.get_attribute("href")
                visible = await el.is_visible()
                print(f"  [{i}] text={repr(text)}, visible={visible}, href={href[:80]}...")

        # Check for mode picker
        mode_btn = page.locator('button[data-test-id="bard-mode-menu-button"]')
        mode_count = await mode_btn.count()
        if mode_count > 0:
            text = await mode_btn.first.inner_text()
            print(f"Mode picker: {text}")
        else:
            print("Mode picker: NOT FOUND")

        # Check for input
        input_el = page.locator('div[contenteditable="true"]')
        input_count = await input_el.count()
        print(f"Input elements: {input_count}")

        # Check if logged in
        visible_sign_in = page.locator('a[href*="accounts.google"]:visible')
        visible_count = await visible_sign_in.count()
        print(f"\nVisible sign-in links: {visible_count}")
        
        if visible_count > 0:
            text = (await visible_sign_in.first.inner_text()).strip()
            if "sign in" in text.lower():
                print("NOT logged in — visible Sign In button found")
            else:
                print(f"Logged in (visible link is not sign-in: {repr(text)})")
                resp = await agent.chat("Say hello in one word")
                print(f"Response: {resp[:200]}")
        else:
            print("Logged in! Trying chat...")
            resp = await agent.chat("Say hello in one word")
            print(f"Response: {resp[:200]}")


asyncio.run(test())
