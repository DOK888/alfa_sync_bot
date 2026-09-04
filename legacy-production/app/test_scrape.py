import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state='auth/tetrika_state.json')
        page = await ctx.new_page()
        
        # Go to fetch URL
        url = 'https://tetrika.s20.online/teacher/1/calendar/fetch?start=2026-06-01&end=2026-07-31&page=1'
        await page.goto(url)
        await page.wait_for_timeout(3000)
        
        # Get raw text
        text = await page.evaluate('() => document.body.innerText')
        
        try:
            data = json.loads(text)
            print(f"Found JSON! Collection size: {len(data.get('collection', []))}")
            if data.get('collection'):
                print("Sample item:", data['collection'][0])
        except Exception as e:
            print("Failed to parse JSON:", e)
            print("Raw text:", text[:200])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
