import asyncio
import aiohttp
from selectolax.parser import HTMLParser
import random
from datetime import datetime
from dateutil.parser import parse as parse_date
import pandas as pd

from playwright.async_api import async_playwright
import sys
import os
from urllib.parse import urlparse
sys.path.append(os.path.dirname(__file__))  # or one level higher if needed

import fieldrules


class AsyncHTMLScraper:
    def __init__(self, urls, field_rules = fieldrules.field_rules_article_basic):
        """
        :param urls: List of URLs to fetch.
        :param field_rules: Dict of field_name: CSS selector or callable.
               e.g., {"title": "title"} or {"custom": lambda tree: tree.css_first("meta[name='description']").attributes.get("content", "")}
        """
        self.urls = urls
        self.field_rules = field_rules
        self.results = []
        self.parsed_count = 0
        self.semaphore = asyncio.Semaphore(10)
        self.global_pause = asyncio.Event()
        self.global_pause.set()
        self.pause_lock = asyncio.Lock()

    async def fetch(self, session, url, retries=5):
        print(f"🔎 Fetching {url}")


        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/114.0",
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) Chrome/118.0.0.0 Mobile Safari/537.36",
        ]

        ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.8", "fi-FI,fi;q=0.7"]


        async with self.semaphore:
            for attempt in range(retries + 1):
                if attempt == retries:

                    if self.pause_lock.locked():
                        # If someone else is already pausing, just wait
                        await self.global_pause.wait()
                    else:
                        async with self.pause_lock:
                            print("🌐 Pausing all tasks for 5 seconds to cool down.")
                            self.global_pause.clear()
                            await asyncio.sleep(random.uniform(4, 6))  # ⏸ Cooldown window
                            self.global_pause.set()

                
                try:
                    await asyncio.sleep(0.1 + random.uniform(0.2, 0.8))
                    await self.global_pause.wait()
                    headers = {
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
                        "Referer": "https://www.google.com/",
                    }
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            html = await response.text()
                            print(f"✅ Got HTML for {url}, length = {len(html)}")
                            await asyncio.sleep(random.uniform(0.2, 0.3))
                            with open(f"html_dump.html", "w", encoding="utf-8") as f:
                                f.write(html)
                            return url, html
                        else:
                            await asyncio.sleep(1 * (1.2 ** attempt) + random.uniform(0, 0.3))
                except Exception as e:
                    if attempt == retries:
                        print(f"❌ Final fail for {url}")
            print(f"❌ Giving up on {url}")
            return url, None
    async def fetch_with_playwright(self, url, retries=8):
        print(f"🔎 Fetching {url}")

        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/114.0",
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) Chrome/118.0.0.0 Mobile Safari/537.36",
        ]

        ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.8", "fi-FI,fi;q=0.7"]

        user_agent = random.choice(USER_AGENTS)
        accept_language = random.choice(ACCEPT_LANGUAGES)

        async with self.semaphore:
            for attempt in range(int(retries) + 1):
                try:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context(
                            user_agent=user_agent,
                            locale=accept_language,
                            java_script_enabled=True,
                            extra_http_headers={
                                "Referer": "https://www.google.com/",
                            }
                        )
                        page = await context.new_page()
                        await page.goto(url, timeout=15000)
                        await self.wait_for_non_empty_content(page, 'meta[itemprop="datePublished"]', attribute="content")
                        await self.wait_for_non_empty_content(page, '[itemprop="text"]')  # innerText based
 
                        await asyncio.sleep(1)
                        
                        html = await page.content()
                        await browser.close()

                        print(f"✅ Got HTML for {url}, length = {len(html)}")
                        await asyncio.sleep(random.uniform(0.2, 0.3))
                        return url, html

                except Exception as e:
                    print(f"⚠️ Attempt {attempt + 1} failed for {url}: {e}")
                    await asyncio.sleep(1 * (2 ** attempt) + random.uniform(0, 0.5))

            print(f"❌ Giving up on {url}")
            return url, None
    def extract_fields(self, html):
        tree = HTMLParser(html)
        extracted = {}
        for key, rule in self.field_rules.items():
            try:
                if callable(rule):
                    extracted[key] = rule(tree)
                else:
                    node = tree.css_first(rule)
                    extracted[key] = node.text() if node else ""
            except Exception:
                extracted[key] = None
        extracted["scrape_time"] = datetime.now()
        return extracted

    async def scrape(self):
        print(f"Scraping")
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch(session, url) for url in self.urls]
            print(tasks)
            
            for i, future in enumerate(asyncio.as_completed(tasks), 1):
                url, html = await future
                if html:
                    self._apply_domain_rules(url)
                    fields = self.extract_fields(html)
                    self.results.append({"url": url, **fields})
                self.parsed_count += 1
                if self.parsed_count % 100 == 0 or self.parsed_count == len(self.urls):
                    
                    print(f"Parsed {self.parsed_count}/{len(self.urls)} pages")
        return pd.DataFrame(self.results)
    

    
    
    #Crawl paginated archives by appending ?page=N to each base URL until no results are found.
    #Stops early when a page returns empty field extraction.
    async def scrape_paginated_archives(self, base_urls=None, min_date=None, max_pages_fallback=30):
        if base_urls is None:
            base_urls = self.urls

        async with aiohttp.ClientSession() as session:
            for base_url in base_urls:
                # Fetch page 1 first
                url_page_1 = f"{base_url}?page=1"
                _, html = await self.fetch(session, url_page_1)
                if not html:
                    print(f"❌ Page 1 failed for {base_url}")
                    continue

                total_pages = self.extract_max_pages_maritime(html) or max_pages_fallback
                print(f"📄 Found {total_pages} pages for {base_url}")

                # Handle page 1 manually
                fields = self.extract_fields(html)
                self.results.append({"url": url_page_1, **fields})
                self.parsed_count += 1

                # Prepare remaining URLs
                urls_to_fetch = [f"{base_url}?page={p}" for p in range(2, total_pages + 1)]

                # Fetch concurrently
                tasks = [self.fetch(session, url) for url in urls_to_fetch]
                responses = await asyncio.gather(*tasks)

                # Process results
                for url, html in responses:
                    if not html:
                        continue
                    fields = self.extract_fields(html)

                    self.results.append({"url": url, **fields})
                    self.parsed_count += 1
                    if self.parsed_count % 10 == 0:
                        print(f"✅ Parsed {self.parsed_count} pages so far")
                    if self.parsed_count % 25 == 0:
                        print(f"✅ Parsed {self.parsed_count} pages so far")
                        await asyncio.sleep(random.uniform(4, 10))

        return self.results
    

## this will be in a python file where field-rules are defined



    #made for maritime
    def extract_max_pages_maritime(self, html):
        if not html:
            return 1
        tree = HTMLParser(html)
        page_links = tree.css("ul.pagination a[href*='?page=']")
        page_numbers = []
        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        for a in page_links:
            print("Found page link:", a.text(strip=True), "href:", a.attributes.get("href"))
            try:
                num = int(a.text(strip=True))
                page_numbers.append(num)
            except ValueError:
                continue  # skip "..." and non-number links

        return max(page_numbers) if page_numbers else 1
    
    def is_page_above_min_date(articles, min_date: datetime) -> bool:
        
        for article in articles:
            date_str = article.get("date", "").strip()
            try:
                if parse_date(date_str) >= min_date:
                    return True
            except Exception:
                continue  # Ignore invalid date strings
        return False  # All dates are older or unparseable
    

    async def wait_for_non_empty_content(page, selector, attribute=None, timeout=8000):
        async def is_filled():
            try:
                element = await page.query_selector(selector)
                if not element:
                    return False
                if attribute:
                    attr_val = await element.get_attribute(attribute)
                    return attr_val and attr_val.strip() != ""
                else:
                    text = await element.inner_text()
                    return text.strip() != ""
            except Exception:
                return False
        await page.wait_for_function(
            is_filled, timeout=timeout
        )



    def _apply_domain_rules(self, url):

        parsed = urlparse(url)
        domain = parsed.hostname
        

        if domain in fieldrules.DOMAIN_FIELD_RULES:
            self.field_rules = fieldrules.DOMAIN_FIELD_RULES[domain]
        else:
            print(f"⚠️ No custom rules found for {domain}, using existing field_rules.")

