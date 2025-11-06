#!/usr/bin/env python3
"""Diagnose Gemini thinking extraction:
1. Send a reasoning question
2. Check for "Show thinking" button
3. Check thoughts-container/model-thoughts
4. Try clicking the button and extracting
"""

import asyncio
import json
from pathlib import Path

async def diagnose():
    from camoufox.async_api import AsyncCamoufox

    state = json.loads(Path("storage/gemini_storage_state.json").read_text())

    async with AsyncCamoufox(headless=True, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        if state.get("cookies"):
            await ctx.add_cookies(state["cookies"])

        page = await ctx.new_page()
        await page.goto("https://gemini.google.com", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("div[contenteditable='true']", state="visible", timeout=30000)
        print(f"URL: {page.url}")

        # Type and submit a reasoning question
        input_el = page.locator("div[contenteditable='true']").first
        await input_el.click()
        await page.wait_for_timeout(300)
        await page.keyboard.insert_text("What is the 10th prime number? Think through each one carefully.")
        await page.wait_for_timeout(1000)

        send_btn = page.locator("button[aria-label='Send message']").first
        if await send_btn.is_visible(timeout=2000):
            await send_btn.click()
            print("Sent message")

        # Wait for response
        print("Waiting for response...")
        for i in range(60):
            await page.wait_for_timeout(1000)
            count = await page.locator(".response-container-content .markdown").count()
            if count > 0 and i >= 10:
                text = await page.locator(".response-container-content .markdown").last.text_content()
                if text and "29" in text:
                    print(f"  t={i+1}s: Response complete (contains '29')")
                    break
            if i % 10 == 9:
                print(f"  t={i+1}s: still waiting...")

        # Give extra time for thinking UI to render
        await page.wait_for_timeout(3000)

        # Now inspect for thinking-related DOM elements
        print("\n=== THINKING DOM INSPECTION ===")

        thinking_inspection = await page.evaluate("""() => {
            const results = {};
            
            // All responses
            const responses = document.querySelectorAll(
                'model-response, .model-response, [data-message-author-role="assistant"]'
            );
            results.responseCount = responses.length;
            
            const lastResponse = responses[responses.length - 1];
            if (!lastResponse) return { error: 'No response elements found' };
            
            // Check for thoughts container
            const thoughtsSelectors = [
                '[data-test-id="model-thoughts"]',
                '.thoughts-container',
                '.thoughts-header',
                '.thoughts-header-button',
                '.thoughts-content',
                '[data-test-id="thoughts-header-button"]',
                'details',
                '[aria-expanded]',
                'button[aria-label*="thinking"]',
                'button[aria-label*="Thinking"]',
                'button[aria-label*="Show thinking"]',
                'button[aria-label*="thought"]',
            ];
            
            for (const sel of thoughtsSelectors) {
                // Check in last response
                const inResponse = lastResponse.querySelectorAll(sel);
                // Check in whole page
                const inPage = document.querySelectorAll(sel);
                if (inResponse.length > 0 || inPage.length > 0) {
                    results[sel] = {
                        inResponse: inResponse.length,
                        inPage: inPage.length,
                        firstText: (inResponse[0] || inPage[0])?.textContent?.trim()?.substring(0, 200) || '',
                        firstHTML: (inResponse[0] || inPage[0])?.outerHTML?.substring(0, 300) || '',
                        visible: (inResponse[0] || inPage[0])?.offsetWidth > 0,
                        ariaExpanded: (inResponse[0] || inPage[0])?.getAttribute('aria-expanded'),
                    };
                }
            }
            
            // Find ALL buttons in last response
            const buttons = lastResponse.querySelectorAll('button, [role="button"]');
            results.buttonsInLastResponse = Array.from(buttons).map(b => ({
                text: (b.textContent || '').trim().substring(0, 80),
                ariaLabel: b.getAttribute('aria-label') || '',
                classes: b.className?.toString()?.substring(0, 100) || '',
                visible: b.offsetWidth > 0 && b.offsetHeight > 0,
                ariaExpanded: b.getAttribute('aria-expanded'),
            })).filter(b => b.visible);
            
            // Find elements with "think" in any attribute or text
            const allElements = lastResponse.querySelectorAll('*');
            const thinkElements = [];
            for (const el of allElements) {
                const text = (el.textContent || '').toLowerCase();
                const cls = (el.className?.toString() || '').toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                
                if (text.includes('think') || cls.includes('think') || 
                    aria.includes('think') || cls.includes('thought')) {
                    thinkElements.push({
                        tag: el.tagName,
                        text: el.textContent?.trim()?.substring(0, 100) || '',
                        classes: el.className?.toString()?.substring(0, 100) || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                    });
                }
            }
            results.thinkElements = thinkElements.slice(0, 20);
            
            // Check the thoughts-container specifically
            const tc = lastResponse.querySelector('.thoughts-container');
            if (tc) {
                results.thoughtsContainerHTML = tc.outerHTML.substring(0, 1000);
                results.thoughtsContainerText = tc.textContent?.trim()?.substring(0, 500) || '';
                results.thoughtsContainerChildren = Array.from(tc.children).map(c => ({
                    tag: c.tagName,
                    classes: c.className?.toString()?.substring(0, 100) || '',
                    text: c.textContent?.trim()?.substring(0, 200) || '',
                    visible: c.offsetWidth > 0 && c.offsetHeight > 0,
                }));
            }
            
            return results;
        }""")

        print(json.dumps(thinking_inspection, indent=2))

        # Screenshot
        await page.screenshot(path="storage/gemini_thinking_dom.png", full_page=False)
        print("\nScreenshot saved")

if __name__ == "__main__":
    asyncio.run(diagnose())
