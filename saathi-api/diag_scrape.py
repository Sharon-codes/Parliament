import asyncio
import httpx
from urllib.parse import quote

async def diagnostic():
    query = "world news"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        res = await client.get(url, headers=headers)
        print(f"STATUS: {res.status_code}")
        with open("ddg_diag.html", "w", encoding="utf-8") as f:
            f.write(res.text)
        print("Scrape saved to ddg_diag.html")

if __name__ == "__main__":
    asyncio.run(diagnostic())
