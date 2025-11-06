"""CLI entry point to save a browser login session for a provider.

Usage:
    python -m universal_agents.browser.save_login claude
    python -m universal_agents.browser.save_login gemini
    python -m universal_agents.browser.save_login gpt
    python -m universal_agents.browser.save_login pplx
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROVIDER_URLS: dict[str, str] = {
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "gpt": "https://chat.openai.com",
    "pplx": "https://www.perplexity.ai",
}

STORAGE_ENV_VARS: dict[str, str] = {
    "claude": "CLAUDE_STORAGE_STATE",
    "gemini": "GEMINI_STORAGE_STATE",
    "gpt": "GPT_STORAGE_STATE",
    "pplx": "PPLX_STORAGE_STATE",
}


async def save_login(provider: str, output_path: str | None = None) -> None:
    from playwright.async_api import async_playwright

    if provider not in PROVIDER_URLS:
        print(f"Unknown provider '{provider}'. Choose from: {', '.join(PROVIDER_URLS)}")
        sys.exit(1)

    url = PROVIDER_URLS[provider]
    out = output_path or f"storage/{provider}_session.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    print(f"Opening {url} in a visible browser window.")
    print("Log in, then press ENTER here to save the session.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url)

        input("Press ENTER after logging in...")

        await context.storage_state(path=out)
        await browser.close()

    print(f"Session saved to {out}")
    env_var = STORAGE_ENV_VARS[provider]
    print(f"Set {env_var}={out} in your .env file to use it.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m universal_agents.browser.save_login <provider>")
        print(f"Providers: {', '.join(PROVIDER_URLS)}")
        sys.exit(1)

    provider = sys.argv[1].lower()
    output = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(save_login(provider, output))


if __name__ == "__main__":
    main()
