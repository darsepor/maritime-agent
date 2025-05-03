

#from __future__ import annotations
import asyncio, csv
from pathlib import Path
from dataclasses import dataclass, asdict
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page
import time

#Target num of articles or call main with target_articles
TARGET_ARTICLES = 100   # ← how many articles you want
# ───────────────────────────────────────────────────────────────────────────

BASE  = "https://www.kongsberg.com"
LIST  = f"{BASE}/maritime/news-and-events/news-archive/"

# ================================================================ dataclass
@dataclass
class Article:
    url: str
    title: str
    date: str
    body_text: str
    segment: str
    keywords: list[str]
# ===================================================== Playwright helpers
async def _block_assets(page: Page):
    await page.route(
        "**/*",
        lambda r: r.abort()
        if r.request.resource_type in ("image", "stylesheet", "font")
        else r.continue_(),
    )

async def _collect_urls() -> list[str]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080}  # Avoid layout shifts
        )
        page = await context.new_page()
        
        # Block more resources to speed up loading
        await page.route("**/*.{png,jpg,jpeg,gif,svg,webp}", lambda route: route.abort())
        await page.route("**/*.css", lambda route: route.abort())
        await page.route("**/*.woff2", lambda route: route.abort())
        
        await page.goto(LIST, wait_until="domcontentloaded")  # Don't wait for full load
        await page.wait_for_selector('a[href*="/news-archive/"]')  # Ensure content loaded

        urls = set()
        last_count = 0
        attempts = 0
        max_attempts = 10  # Prevent infinite loops
        last_urls = 0
        num_fails = 0
        while len(urls) < TARGET_ARTICLES and attempts < max_attempts:
            # Get all current links at once
            links = await page.query_selector_all('a[href*="/news-archive/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href and "/news-archive/" in href:
                    full_url = href if href.startswith("http") else f"{BASE}{href}"
                    urls.add(full_url)
            
            # Stop if we've reached our target
            if len(urls) >= TARGET_ARTICLES:
                break
            
            # Only click if we got new links last time
            if len(urls) > last_count:
                last_count = len(urls)
                attempts = 0
                
                # More reliable click with waiting
                try:
                    load_more = await page.query_selector('button:has-text("Load more"), a:has-text("Load more")')
                    if load_more:
                        await load_more.scroll_into_view_if_needed()
                        await load_more.click(timeout=300)
                        await page.wait_for_timeout(200)  # Short wait for new content
                except Exception as e:
                    print(f"[debug] Load more click failed: {e}")
                    break
            else:
                attempts += 1
                await page.wait_for_timeout(200)  # Short wait before retry
            print("num urls", len(urls))

            # IN case of fail wait, in case of 5 consecutive fails break
            if last_urls == len(urls):
                num_fails += 1
                print("sleeping")
                time.sleep(4)
                print("Wake up!")
                if num_fails > 5:
                    print("Breaking")
                    break
                if num_fails > 1:
                    print("big sleep")
                    time.sleep(10)
                    print("Wake up!")
            else:
                num_fails = 0

            last_urls = len(urls)
        await browser.close()
        return list(urls)[:TARGET_ARTICLES]

# ===================================================== Detail fetchers
async def _fetch_article(client: httpx.AsyncClient, url: str) -> Article | None:
    try:
        r = await client.get(url)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] failed {url} -> {e}")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.find("h1").get_text(strip=True)
    date_tag = soup.find("time") or soup.find(class_="news-date")
    date = date_tag.get_text(strip=True) if date_tag else ""
    # ── segment ──────────────────────────────────────────────────────────
    seg_tag = soup.find(class_="news-tag")
    segment = seg_tag.get_text(strip=True) if seg_tag else ""
    # ── keywords (meta) ───────────────────────────────────────────────────
    kw_meta = soup.find("meta", attrs={"name": "keywords"})
    keywords = (
        [k.strip() for k in kw_meta["content"].split(",") if k.strip()]
        if kw_meta and kw_meta.get("content")
        else []
    )
    body = soup.find("article") or soup
    return Article(
    url=url,
    title=title,
    date=date,
    body_text=body.get_text(" ", strip=True),
    segment=segment,
    keywords=keywords  )

# ===================================================== Main orchestration
async def main(target_articles=TARGET_ARTICLES):
    urls = await _collect_urls()
    async with httpx.AsyncClient(headers={"User-Agent": "km-fast-scraper/1.1"}, timeout=httpx.Timeout(15, connect=30)) as client:
        sem = asyncio.Semaphore(10)
        articles: list[Article] = []

        async def bound(url):
            async with sem:
                art = await _fetch_article(client, url)
                if art:
                    articles.append(art)

        await asyncio.gather(*(bound(u) for u in urls))

    #Save file as csv
    file_name = f"blog_posts_{len(articles)}"
    columns = [("title", "title"), ("body_text","text"), ("keywords", "keywords"), ("segment", "segment") ,("date", "date"),("url", "url")]

    with Path(f"{file_name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # Write custom headers
        w.writerow([col[1] for col in columns])  # second item is display name
        for a in articles:
            row = asdict(a)
            row["keywords"] = "|".join(row["keywords"])  # flatten list
            # Write values in your chosen order
            w.writerow([row[col[0]] for col in columns])

if __name__ == "__main__":
    asyncio.run(main())
