#!/usr/bin/env python3
"""Probe Gemini upload UI elements to find working selectors."""

import asyncio
import json
from pathlib import Path


JS_PROBE = """() => {
    const data = {};

    // Hidden file upload buttons
    const hidden = document.querySelectorAll('button[data-test-id*="upload"], button[data-test-id*="file"]');
    data.hidden_buttons = Array.from(hidden).map(b => ({
        testId: b.getAttribute('data-test-id'),
        visible: b.offsetParent !== null,
        ariaLabel: b.getAttribute('aria-label'),
        html: b.outerHTML.substring(0, 300)
    }));

    // Upload/file-related buttons
    const uploadBtn = document.querySelectorAll('button[aria-label*="upload" i], button[aria-label*="file" i]');
    data.upload_buttons = Array.from(uploadBtn).map(b => ({
        ariaLabel: b.getAttribute('aria-label'),
        testId: b.getAttribute('data-test-id'),
        visible: b.offsetParent !== null,
        html: b.outerHTML.substring(0, 300)
    }));

    // File inputs
    const fileInputs = document.querySelectorAll('input[type="file"]');
    data.file_inputs = Array.from(fileInputs).map(i => ({
        accept: i.accept,
        multiple: i.multiple,
        name: i.name,
        id: i.id,
        visible: i.offsetParent !== null,
        html: i.outerHTML.substring(0, 300)
    }));

    // Attach / add buttons
    const attachBtns = document.querySelectorAll('button[aria-label*="Attach" i], button[aria-label*="Add" i]');
    data.attach_buttons = Array.from(attachBtns).map(b => ({
        ariaLabel: b.getAttribute('aria-label'),
        visible: b.offsetParent !== null,
        testId: b.getAttribute('data-test-id'),
        html: b.outerHTML.substring(0, 300)
    }));

    // All buttons in the page (with aria-label)
    const allBtns = document.querySelectorAll('button[aria-label]');
    data.all_labeled_buttons = Array.from(allBtns).map(b => ({
        ariaLabel: b.getAttribute('aria-label'),
        testId: b.getAttribute('data-test-id'),
        visible: b.offsetParent !== null,
    })).filter(b => b.visible);

    return data;
}"""


async def probe():
    from camoufox.async_api import AsyncCamoufox

    state_path = "compiled_agents/gemini_kendo_srt_translator/storage/gemini_storage_state.json"
    state = json.loads(Path(state_path).read_text())
    cookies = state.get("cookies", [])

    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900}, locale="en-US"
        )
        page = await ctx.new_page()
        await ctx.add_cookies(cookies)
        await page.goto("https://gemini.google.com")
        await page.wait_for_selector(
            "div[contenteditable='true']", state="visible", timeout=30000
        )
        await asyncio.sleep(3)

        results = await page.evaluate(JS_PROBE)
        print(json.dumps(results, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(probe())
