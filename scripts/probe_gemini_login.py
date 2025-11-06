#!/usr/bin/env python3
"""Probe Gemini page for login state indicators."""

import asyncio
import json
from pathlib import Path


async def probe():
    from camoufox.async_api import AsyncCamoufox

    state_path = Path("storage/gemini_storage_state.json")

    for label, use_cookies in [("WITHOUT cookies", False), ("WITH cookies", True)]:
        print(f"\n{'='*60}")
        print(f"  Testing {label}")
        print(f"{'='*60}\n")

        async with AsyncCamoufox(headless=False, humanize=True) as browser:
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 900}, locale="en-US"
            )
            if use_cookies and state_path.exists():
                state = json.loads(state_path.read_text())
                if state.get("cookies"):
                    await ctx.add_cookies(state["cookies"])

            page = await ctx.new_page()
            await page.goto("https://gemini.google.com")

            try:
                await page.wait_for_selector(
                    'div[contenteditable="true"]', state="visible", timeout=15000
                )
            except Exception:
                print("  No chat input found within 15s")

            await asyncio.sleep(4)

            # Check for login indicators
            checks = {
                "chat_input": 'div[contenteditable="true"]',
                "sign_in_button": 'a[href*="accounts.google.com"]',
                "sign_in_text": 'text="Sign in"',
                "user_avatar": 'img[aria-label*="Account"]',
                "profile_btn": 'a[aria-label*="Account"]',
                "profile_btn2": 'button[aria-label*="Account"]',
                "profile_btn3": 'a[aria-label*="Google Account"]',
                "gbwa_button": "#gbwa",
                "mode_picker": 'button[data-test-id="bard-mode-menu-button"]',
            }

            for name, sel in checks.items():
                try:
                    count = await page.locator(sel).count()
                    if count > 0:
                        text = ""
                        try:
                            text = await page.locator(sel).first.inner_text()
                            text = text.strip()[:80]
                        except Exception:
                            pass
                        href = ""
                        try:
                            href = await page.locator(sel).first.get_attribute("href") or ""
                            href = href[:80]
                        except Exception:
                            pass
                        print(f"  ✅ {name}: count={count}, text={repr(text)}, href={repr(href)}")
                    else:
                        print(f"  ❌ {name}: not found")
                except Exception as e:
                    print(f"  ⚠️  {name}: error - {e}")

            # Check mode picker details
            mode_btn = page.locator('button[data-test-id="bard-mode-menu-button"]')
            if await mode_btn.count() > 0:
                text = (await mode_btn.first.inner_text()).strip()
                print(f"\n  Mode picker text: {repr(text)}")

                # Open menu and check items
                await mode_btn.first.click()
                await asyncio.sleep(1.5)

                items = page.locator('[role="menu"] [role="menuitem"]')
                count = await items.count()
                print(f"  Menu items ({count}):")
                for i in range(count):
                    item = items.nth(i)
                    item_text = (await item.inner_text()).strip()
                    disabled = await item.get_attribute("disabled")
                    aria_disabled = await item.get_attribute("aria-disabled")
                    test_id = await item.get_attribute("data-test-id") or ""
                    print(
                        f"    [{i}] {repr(item_text[:60])} "
                        f"disabled={disabled} aria-disabled={aria_disabled} "
                        f"test-id={test_id}"
                    )
                await page.keyboard.press("Escape")

            # JS-based deep check for user profile / sign-in
            login_info = await page.evaluate("""() => {
                const results = {};

                // Check for sign-in links
                const signInLinks = document.querySelectorAll('a[href*="accounts.google"]');
                results.signInLinks = Array.from(signInLinks).map(a => ({
                    text: a.innerText.trim().substring(0, 60),
                    href: a.href.substring(0, 100)
                }));

                // Check for profile images
                const profileImgs = document.querySelectorAll('img[src*="googleusercontent"]');
                results.profileImages = profileImgs.length;

                // Look for any element with "sign in" text
                const allEls = document.querySelectorAll('a, button, span');
                results.signInElements = [];
                for (const el of allEls) {
                    const text = (el.innerText || '').toLowerCase();
                    if (text.includes('sign in') || text.includes('log in')) {
                        results.signInElements.push({
                            tag: el.tagName,
                            text: el.innerText.trim().substring(0, 60),
                            className: (el.className || '').substring(0, 60)
                        });
                    }
                }

                return results;
            }""")
            print(f"\n  JS Login check:")
            print(f"    Sign-in links: {login_info.get('signInLinks', [])}")
            print(f"    Profile images: {login_info.get('profileImages', 0)}")
            print(f"    Sign-in elements: {login_info.get('signInElements', [])}")

            await browser.close()


asyncio.run(probe())
