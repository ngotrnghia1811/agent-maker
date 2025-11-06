#!/usr/bin/env python3
"""Test file upload on Claude.ai - tries multiple strategies."""
import asyncio
import tempfile
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

    # Create a small test file
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="test_upload_", delete=False)
    tmp.write("This is a test file uploaded by the automation script.\nPlease respond with 'UPLOAD_OK'.")
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()
    print(f"Test file: {tmp_path}")

    # ===== Strategy A: Click "Add files" button and look for menu items =====
    print("\n--- Strategy A: Add files button → menu → file chooser ---")
    try:
        btn = page.locator('button[aria-label*="Add files"]').first
        if await btn.count() > 0:
            print("  Found 'Add files' button, clicking...")
            await btn.click()
            await page.wait_for_timeout(1000)

            # Check what appeared
            menu_items = page.locator('[role="menuitem"], [role="option"], button[class*="menu"], [class*="dropdown"] button, [class*="popover"] button')
            count = await menu_items.count()
            print(f"  Found {count} menu-like elements:")
            for i in range(min(count, 15)):
                item = menu_items.nth(i)
                try:
                    text = (await item.text_content() or "").strip()[:80]
                    visible = await item.is_visible()
                    tag = await item.evaluate("e => e.tagName")
                    if visible and text:
                        print(f"    [{i}] {tag}: '{text}'")
                except:
                    pass

            # Also check for any new visible elements
            all_visible = page.locator('[role="dialog"] :visible, [class*="popover"] :visible, [class*="dropdown"] :visible')
            vc = await all_visible.count()
            print(f"  Found {vc} visible elements in overlays")

            # Look for file-related menu items
            for text_match in ["computer", "file", "upload", "local"]:
                try:
                    item = page.locator(f'button:has-text("{text_match}"), [role="menuitem"]:has-text("{text_match}"), a:has-text("{text_match}")').first
                    if await item.count() > 0 and await item.is_visible():
                        print(f"  Found '{text_match}' item, clicking with file chooser...")
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await item.click()
                        fc = await fc_info.value
                        await fc.set_files(tmp_path)
                        print("  ✅ FILE UPLOADED via menu!")
                        await page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    print(f"  Menu item '{text_match}' failed: {e}")

            # Dismiss menu if still open
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
    except Exception as e:
        print(f"  Strategy A failed: {e}")

    # ===== Strategy B: Direct set_input_files with event dispatch =====
    print("\n--- Strategy B: Direct input set_input_files + dispatch event ---")
    try:
        # Navigate to fresh page first
        await page.goto("https://claude.ai/new")
        await page.wait_for_load_state("networkidle", timeout=30_000)

        locator = page.locator('input[data-testid="file-upload"]').first
        if await locator.count() > 0:
            await locator.set_input_files(tmp_path)
            print("  set_input_files called, dispatching events...")
            # Dispatch change and input events to trigger React
            await page.evaluate("""() => {
                const input = document.querySelector('input[data-testid="file-upload"]');
                if (input) {
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }""")
            await page.wait_for_timeout(3000)
            # Check if file appeared in the UI
            file_indicators = page.locator('[class*="file"], [class*="attachment"], [class*="upload"], [data-testid*="file"]')
            fc = await file_indicators.count()
            print(f"  File indicators found: {fc}")
            for i in range(min(fc, 5)):
                try:
                    el = file_indicators.nth(i)
                    text = (await el.text_content() or "").strip()[:80]
                    visible = await el.is_visible()
                    if visible:
                        print(f"    [{i}]: '{text}'")
                except:
                    pass
    except Exception as e:
        print(f"  Strategy B failed: {e}")

    # ===== Strategy C: Click "Add files" → expect file chooser directly =====
    print("\n--- Strategy C: Click Add files → expect file chooser directly ---")
    try:
        await page.goto("https://claude.ai/new")
        await page.wait_for_load_state("networkidle", timeout=30_000)

        btn = page.locator('button[aria-label*="Add files"]').first
        if await btn.count() > 0:
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await btn.click()
            fc = await fc_info.value
            await fc.set_files(tmp_path)
            print("  ✅ FILE UPLOADED via direct file chooser!")
            await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  Strategy C failed: {e}")

    input("\nPress Enter to close browser...")
    await mgr.close()


asyncio.run(main())
