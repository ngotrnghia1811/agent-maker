"""Debug script to inspect Claude's DOM for file upload selectors."""
import asyncio
import sys
sys.path.insert(0, "src")

from universal_agents.providers.claude.data import ClaudeDataAgent
from universal_agents.providers.claude.config import ClaudeDataConfig


async def inspect():
    config = ClaudeDataConfig(
        headless=False,
        storage_state="storage/claude_storage_state.json",
        timeout=60,
    )
    agent = ClaudeDataAgent(config)
    await agent.__aenter__()

    try:
        page = await agent._ensure_ready()
        print("Page loaded and navigated, waiting for UI...")
        await page.wait_for_timeout(5000)

        # Check for file inputs
        file_inputs = await page.query_selector_all('input[type="file"]')
        print(f"File inputs found: {len(file_inputs)}")
        for i, inp in enumerate(file_inputs):
            attrs = await inp.evaluate(
                """el => ({
                    id: el.id, name: el.name, accept: el.accept,
                    display: getComputedStyle(el).display,
                    visibility: getComputedStyle(el).visibility,
                    className: el.className, hidden: el.hidden,
                    parentTag: el.parentElement?.tagName,
                    width: el.offsetWidth, height: el.offsetHeight
                })"""
            )
            print(f"  Input {i}: {attrs}")

        # Check ALL buttons
        buttons = await page.query_selector_all("button")
        print(f"\nTotal buttons: {len(buttons)}")
        for btn in buttons:
            aria = await btn.get_attribute("aria-label") or ""
            testid = await btn.get_attribute("data-testid") or ""
            text = (await btn.inner_text()).strip()[:60]
            keywords = ["attach", "upload", "file", "add", "clip", "paper", "content"]
            if any(k in (aria + testid + text).lower() for k in keywords):
                print(f'  Button: aria="{aria}" data-testid="{testid}" text="{text}"')

        # Also list ALL button aria-labels for reference
        print("\nAll button aria-labels:")
        for btn in buttons:
            aria = await btn.get_attribute("aria-label") or ""
            testid = await btn.get_attribute("data-testid") or ""
            if aria or testid:
                print(f'  aria="{aria}" testid="{testid}"')

        # Check for elements with relevant attributes
        js_code = """() => {
            const results = [];
            const selectors = [
                '[aria-label*="file" i]', '[aria-label*="attach" i]',
                '[aria-label*="upload" i]', '[aria-label*="content" i]',
                '[data-testid*="file" i]', '[data-testid*="attach" i]',
                '[data-testid*="upload" i]',
            ];
            for (const sel of selectors) {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        results.push({
                            tag: el.tagName,
                            ariaLabel: el.getAttribute('aria-label'),
                            testId: el.getAttribute('data-testid'),
                            role: el.getAttribute('role'),
                            className: (el.className?.substring?.(0, 80)) || '',
                        });
                    });
                } catch(e) {}
            }
            return results;
        }"""
        attach_elems = await page.evaluate(js_code)
        print(f"\nElements with file/attach/upload/content in attributes: {len(attach_elems)}")
        for e in attach_elems:
            print(f"  {e}")

        # Check SVG icon-only buttons
        svg_buttons = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('button svg, button path').forEach(el => {
                const btn = el.closest('button');
                if (btn) {
                    const aria = btn.getAttribute('aria-label') || '';
                    const testid = btn.getAttribute('data-testid') || '';
                    const parentHTML = btn.outerHTML.substring(0, 300);
                    const text = btn.innerText?.trim();
                    if (!text || text.length < 3) {
                        results.push({aria, testid, html: parentHTML});
                    }
                }
            });
            const seen = new Set();
            return results.filter(r => {
                if (seen.has(r.html)) return false;
                seen.add(r.html);
                return true;
            });
        }""")
        print(f"\nIcon-only buttons with SVGs: {len(svg_buttons)}")
        for s in svg_buttons:
            print(f'  aria="{s["aria"]}" testid="{s["testid"]}"')
            print(f'    HTML: {s["html"][:300]}')

    finally:
        await agent.__aexit__(None, None, None)


asyncio.run(inspect())
