#!/usr/bin/env python3
"""Standalone YouTube channel video scraper using Playwright.
Usage: python3 _scrape_channel.py <channel_id> <max_results> [handle]
"""
import asyncio, json, sys

async def main():
    channel_id = sys.argv[1] if len(sys.argv) > 1 else "UCqKGbJcY5eCxMq6fBIA6aoQ"
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    handle = sys.argv[3] if len(sys.argv) > 3 else ""

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0"
        )

        if handle:
            url = "https://www.youtube.com/" + handle + "/videos"
        else:
            url = "https://www.youtube.com/channel/" + channel_id + "/videos"

        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)

        # Extract videos using confirmed-working selector
        videos = await page.evaluate("""() => {
            var items = [];
            document.querySelectorAll('h3 a[href*="/watch"]').forEach(function(link) {
                if (items.length >= MAX_PLACEHOLDER) return;
                var m = link.href.match(/v=([a-zA-Z0-9_-]{11})/);
                if (m) items.push({id: m[1], title: (link.textContent || '').trim()});
            });
            return items;
        }""".replace("MAX_PLACEHOLDER", str(max_results)))

        print(json.dumps(videos))
        await browser.close()

asyncio.run(main())
