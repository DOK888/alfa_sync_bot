import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state='/workspace/auth/tetrika_state.json')
        page = await context.new_page()
        res = await page.goto('https://tetrika.s20.online/teacher/1/calendar/fetch?start=2026-06-01&end=2026-06-05&page=1')
        data = await res.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        await browser.close()
asyncio.run(main())
