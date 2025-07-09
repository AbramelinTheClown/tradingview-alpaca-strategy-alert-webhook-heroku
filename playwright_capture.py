import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DUMP_DIR = Path(os.getenv("BROWSER_DUMP_DIR", "D:/AI_FORGE_COMPLETE_LAB/database/raw_backups/networking"))
DUMP_DIR.mkdir(parents=True, exist_ok=True)

BRAVE_PATH = os.getenv("BRAVE_PATH", r"browser_capture\brave.exe")

DEFAULT_URLS = [
    "https://www.google.com",
]

# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------
async def capture_page(playwright, url: str) -> dict:  # noqa: WPS231
    browser = await playwright.chromium.launch(
        headless=True,
        executable_path=BRAVE_PATH if os.path.isfile(BRAVE_PATH) else None,
        args=["--disable-extensions"]
    )
    context = await browser.new_context()
    page = await context.new_page()

    captured_requests: List[dict] = []
    captured_console: List[dict] = []

    # Event listeners
    context.on("request", lambda req: captured_requests.append({
        "url": req.url,
        "method": req.method,
        "headers": req.headers,
        "timestamp": time.time(),
    }))

    async def handle_response(resp):
        try:
            body = await resp.body()
            captured_requests.append({
                "url": resp.url,
                "status": resp.status,
                "headers": resp.headers,
                "length": len(body),
                "timestamp": time.time(),
            })
        except Exception:
            pass
    context.on("response", lambda res: asyncio.create_task(handle_response(res)))

    def handle_console(msg):
        captured_console.append({
            "type": msg.type,
            "text": msg.text,
            "timestamp": time.time(),
        })
    page.on("console", handle_console)

    await page.goto(url, wait_until="networkidle")
    dom_tree = await page.content()

    storage_state = await context.storage_state()

    result = {
        "page_url": url,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "dom_tree": dom_tree,
        "requests": captured_requests,
        "console_logs": captured_console,
        "storage": storage_state,
    }

    await browser.close()
    return result


async def main(urls: List[str]):
    async with async_playwright() as playwright:
        for url in urls:
            try:
                data = await capture_page(playwright, url)
                file_path = DUMP_DIR / f"browser_{int(time.time()*1000)}.json"
                with file_path.open("w", encoding="utf-8") as fp:
                    json.dump(data, fp, ensure_ascii=False, indent=2)
                logging.info("Captured page %s -> %s", url, file_path)
            except Exception as exc:
                logging.exception("Failed to capture %s: %s", url, exc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture browser data and dump to JSON for vector ingestion")
    parser.add_argument("urls", nargs="*", default=DEFAULT_URLS, help="List of URLs to capture")
    args = parser.parse_args()

    asyncio.run(main(args.urls)) 