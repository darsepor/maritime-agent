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
import re

import fieldrules
import fitz  # PyMuPDF
from io import BytesIO
from urllib.parse import urljoin
import json, re, asyncio
#import pyautogui
import pyperclip
from playwright.sync_api import sync_playwright
import time

class AsyncHTMLScraper:
    def __init__(self, urls, field_rules = fieldrules.field_rules_article_basic, start_date = None, end_date = None, apply_domain_rules = True, get_urls = False):
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
        self.start_date = start_date
        self.end_date = end_date
        self.apply_domain_rules = apply_domain_rules
        self.get_urls = get_urls

    async def fetch_with_fallback(self, session, url):
        domain = urlparse(url).netloc
        url, html = await self.fetch(session, url, raise_on_header_error=True)
        if html is None:
            print(f"🔁 Falling back to Playwright for {url}")
            return await self.fetch_with_playwright(url)
        return url, html


    async def fetch(self, session, url, retries=5, raise_on_header_error=False):   #Given url and rules from self.field_rules extract fields, Handels pausing threads dynamicly to avoid getting blocked/banned
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
                    print("Trying to het a response")
                    async with session.get(url, headers=headers, timeout=10) as response:
                        print("Got response")
                        if response.status == 200:
                            html = await response.text()
                            print(f"✅ Got HTML for {url}, length = {len(html)}")
                            await asyncio.sleep(random.uniform(0.2, 0.3))

                            return url, html
                        else:
                            print(f"❌ Got {response.status} for {url}")
                            await asyncio.sleep(1 * (1.2 ** attempt) + random.uniform(0, 0.3))
                except Exception as e:
                    print(f"⚠️ Exception on attempt {attempt} for {url}: {e}")
                    if "Header value is too long" in str(e):
                        if raise_on_header_error:
                            return url, None  # Let wrapper decide to fallback
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
            for attempt in range(retries + 1):
                try:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context(
                            user_agent=user_agent,
                            locale=accept_language,
                            java_script_enabled=True,
                            extra_http_headers={"Referer": "https://www.google.com/"},
                        )
                        page = await context.new_page()

                        if self.pause_lock.locked():
                            await self.global_pause.wait()

                        await page.goto(url, timeout=15000)
                        await page.wait_for_selector("body", timeout=8000)
                        await asyncio.sleep(1.0 + random.uniform(0.2, 0.5))

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

    async def scrape(self):  #General function to scrape, lists urls as task (to utilise concurrency and parallelism) and passes them to fetch
        
        print(f"Scraping")
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_with_fallback(session, url) for url in self.urls]
            print(tasks)
            last_pause_time = asyncio.get_event_loop().time()
            global_pause = random.uniform(700, 1100)
            for i, future in enumerate(asyncio.as_completed(tasks), 1):
                current_time = asyncio.get_event_loop().time()
                
                if current_time - last_pause_time >= global_pause:  # Default pause to cool down
                    print(f"🌐🌐🌐Large global pause, 30-60s.🌐🌐🌐, total fetched {self.parsed_count}")
                    
                    global_pause = random.uniform(700, 1100)
                    self.global_pause.clear()
                    await asyncio.sleep(random.uniform(30, 60))
                    self.global_pause.set()
                    last_pause_time = current_time
                url, html = await future
                if html:
                    with open(f"html_dump.html", "w", encoding="utf-8") as f:
                        f.write(html)

                    self._apply_domain_rules(url)
                    fields = self.extract_fields(html)
                    self.results.append({"url": url, **fields})
                self.parsed_count += 1
                if self.parsed_count % 100 == 0 or self.parsed_count == len(self.urls):
                    
                    print(f"Parsed {self.parsed_count}/{len(self.urls)} pages")
        if self.get_urls:
            return self.results
        return pd.DataFrame(self.results)
    
    async def scrape_pdfs(self):
        async with aiohttp.ClientSession() as session:
            for url in self.urls:
                try:
                    url, pdf_bytes = await self.fetch_pdf(session, url)
                    if pdf_bytes:
                        try:
                            text = self.decode_pdf_or_text(pdf_bytes)
                            sections = self.extract_sections(text)
                            self.results.append({"url": url, "text": text, **sections})
                        except Exception:
                            continue
                except: continue
                self.parsed_count += 1
                

                
    
        return self.results
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

    def decode_pdf_or_text(self, pdf_bytes):
        """
        Detect if pdf_bytes is a real PDF or just text.

        - If starts with %PDF-, treat as PDF file.
        - Else decode as UTF-8 text.
        """
        if pdf_bytes[:5] == b"%PDF-":
            # Assume it's a real PDF
            doc = fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf")
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            return full_text
        else:
            # Plain text fallback
            return pdf_bytes.decode('utf-8', errors='ignore')

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
    

    async def wait_for_non_empty_content(
            self, page, selector, *, attribute=None, timeout=8000
        ):
            js_expr = """({ sel, attr }) => {
                const el = document.querySelector(sel);
                if (!el) return false;

                if (attr) {
                    const v = el.getAttribute(attr);
                    return v && v.trim() !== "";
                }
                return el.innerText && el.innerText.trim() !== "";
            }"""

            args = {"sel": selector, "attr": attribute}

            print(f"🕒 Waiting for selector='{selector}' attribute='{attribute}' with timeout={timeout}")
            print(f"👉 JS ARGUMENTS PASSED TO BROWSER: {args}")

            try:
                await page.wait_for_function(js_expr, arg=args, timeout=timeout)
            except Exception as e:
                print(f"❌ wait_for_non_empty_content failed for selector='{selector}' with error: {e}")
                raise


    def _apply_domain_rules(self, url):
        if self.apply_domain_rules is False:
            return
        parsed = urlparse(url)
        domain = parsed.hostname
        

        if domain in fieldrules.DOMAIN_FIELD_RULES:
            self.field_rules = fieldrules.DOMAIN_FIELD_RULES[domain]
        else:
            print(f"⚠️ No custom rules found for {domain}, using existing field_rules.")






    ########## for pdf-scraping





   



    async def fetch_pdf_with_playwright(self, url, retries: int = 3):
        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/114.0",
        ]

        for attempt in range(retries):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        java_script_enabled=True,
                    )
                    page = await context.new_page()
                    await page.goto(url, timeout=30000)

                    # Wait until the viewer injects the meta tag
                    await page.wait_for_selector('meta[name="citation_pdf_url"]', timeout=10000)
                    pdf_url = await page.get_attribute('meta[name="citation_pdf_url"]', "content")

                    # same-origin fallback
                    if pdf_url and not pdf_url.startswith("http"):
                        pdf_url = urljoin(url, pdf_url)

                    if not pdf_url:
                        await browser.close()
                        continue

                    # Now download the PDF within Playwright (avoids cookie issues)
                    async with context.request.get(pdf_url, timeout=30000) as response:
                        if response.ok and "pdf" in response.headers.get("Content-Type", ""):
                            pdf_bytes = await response.body()
                            await browser.close()
                            return url, pdf_bytes

                    await browser.close()

            except Exception as e:
                print(f"⚠️  Playwright attempt {attempt+1} failed: {e}")

        return url, None     # ALWAYS return a tuple



    async def fetch_pdf_text_with_playwright(self, url):
        print(f"🔁 [Playwright Fallback - Text Extraction] Trying to extract text from {url}")

        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/114.0",
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) Chrome/118.0.0.0 Mobile Safari/537.36",
        ]

        user_agent = random.choice(USER_AGENTS)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=user_agent,
                    java_script_enabled=True,
                )
                page = await context.new_page()
                await page.goto(url, timeout=30000)

                await asyncio.sleep(3)  # Wait for page to load

                try:
                    # Try to extract text
                    extracted_text = await page.evaluate("""() => {
                        return document.body.innerText;
                    }""")
                except Exception as e:
                    print(f"⚠️ Error extracting text: {e}")
                    extracted_text = None

                await browser.close()

                if extracted_text and extracted_text.strip():
                    print(f"✅ Successfully extracted text, length = {len(extracted_text)} characters")
                    return url, extracted_text.encode('utf-8')
                else:
                    print(f"❌ No text extracted.")
                    return url, None

        except Exception as e:
            print(f"❌ Total failure: {e}")
            return url, None   # <- Always return (url, None) even if crash



    async def _download_ieee_pdf_fast(self, session, viewer_url):
        """
        Try IEEE JSON API first, then <iframe src="…pdf"> inside stamp page.
        Return (viewer_url, pdf_bytes | None)
        """
        # ---- 0) arnumber ----
        m = re.search(r'/(\d+)\.pdf$', viewer_url)
        if not m:
            return viewer_url, None
        ar = m.group(1)

        # ---- 1) public JSON ----
        api = f"https://ieeexplore.ieee.org/rest/document/{ar}"
        try:
            async with session.get(api, timeout=10) as r:
                if r.status == 200:
                    data = json.loads(await r.text())
                    pdf_path = data.get("pdfUrl") or data.get("pdfPath")
                    if pdf_path:
                        pdf_url = urljoin("https://ieeexplore.ieee.org", pdf_path)
                        async with session.get(pdf_url, timeout=25) as resp:
                            if resp.status == 200 and "pdf" in resp.headers.get("Content-Type", ""):
                                return viewer_url, await resp.read()
        except Exception:
            pass

        # ---- 2) stamp page iframe ----
        stamp = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={ar}"
        _, html = await self.fetch(session, stamp, raise_on_header_error=True)
        if not html:
            return viewer_url, None
        tree = HTMLParser(html)
        frame = tree.css_first('iframe[src*=".pdf"]')
        if frame:
            pdf_url = urljoin(stamp, frame.attributes["src"])
            async with session.get(pdf_url, timeout=25) as resp:
                if resp.status == 200 and "pdf" in resp.headers.get("Content-Type", ""):
                    return viewer_url, await resp.read()

        return viewer_url, None


    async def _copy_pdf_text_play_acting(self, viewer_url, *, timeout_ms=30000):
        """
        Visible Playwright tab, small mouse wiggle & Ctrl+A/C inside frame.
        Returns (url, bytes or None).
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                permissions=["clipboard-read", "clipboard-write"],
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(viewer_url, timeout=timeout_ms)

            # wait until a frame navigates to *.pdf
            def _pdf(f): return f.url and f.url.lower().endswith(".pdf")
            try:
                frame = await page.wait_for_event("framenavigated", predicate=_pdf, timeout=15000)
            except Exception:
                await browser.close(); return viewer_url, None

            await page.wait_for_timeout(3000)  # let text render
            await frame.keyboard.press("Control+A")
            await frame.keyboard.press("Control+C")
            txt = await page.evaluate("navigator.clipboard.readText()")
            await browser.close()
            return viewer_url, txt.encode() if txt.strip() else (viewer_url, None)


    def extract_sections(self, text):
        sections = {
            "abstract": "",
            "conclusion": "",
            "references": ""
        }

        # Abstract — match only the first occurrence, non-greedy until next header
        abstract_match = re.search(r'(?i)\babstract\b[\s:\-\.]*\n?(.*?)(\n[A-Z][^\n]{3,})', text, re.DOTALL)
        if abstract_match:
            sections["abstract"] = abstract_match.group(1).strip()

        # Conclusion — non-greedy until next header
        conclusion_match = re.search(r'(?i)\bconclusions?\b[\s:\-\.]*\n?(.*?)(\n[A-Z][^\n]{3,})', text, re.DOTALL)
        if conclusion_match:
            sections["conclusion"] = conclusion_match.group(1).strip()

        # References — grab till end of document
        references_match = re.search(r'(?i)\breferences\b[\s:\-\.]*\n?(.*)', text, re.DOTALL)
        if references_match:
            sections["references"] = references_match.group(1).strip()


        return sections
    ################## for pdf-scraping
    # ──────────────────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────────────────


    # ──────────────────────────────────────────────────────────────────────────────
    #  1) Same fast helper you already use (JSON + iframe download)
    #     — unchanged, skip here for brevity —
    #     name it   _download_ieee_pdf_fast(...)
    # ──────────────────────────────────────────────────────────────────────────────



    # ──────────────────────────────────────────────────────────────────────────────
    #  2) Stage B — intercept any *application/pdf* response
    # ──────────────────────────────────────────────────────────────────────────────
    async def _download_ieee_pdf_intercept(self, viewer_url, *, timeout_ms=20000):
        from playwright.async_api import async_playwright

        pdf_bytes = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # capture first PDF response
            async def handle_response(resp):
                nonlocal pdf_bytes
                if (pdf_bytes is None
                        and "application/pdf" in resp.headers.get("content-type", "")):
                    try:
                        pdf_bytes = await resp.body()
                    except Exception:
                        pass

            context.on("response", handle_response)

            page = await context.new_page()
            await page.goto(viewer_url, timeout=timeout_ms)
            await page.wait_for_timeout(5000)     # let pdf.js fire its request
            await browser.close()

        return viewer_url, pdf_bytes            # may be None
    # ──────────────────────────────────────────────────────────────────────────────



    # ──────────────────────────────────────────────────────────────────────────────
    #  3) Stage C — mouse wiggle + Ctrl+A / Ctrl+C INSIDE Playwright
    # ──────────────────────────────────────────────────────────────────────────────
    async def _copy_pdf_text_real_browser_async(self, viewer_url, wait_sec=15):
        """
        Final fallback: opens a real visible Chrome tab (Playwright async),
        clicks and does Ctrl+A, Ctrl+C inside the window.
        No viewport calls — safe click at fixed coordinates.
        """
        from playwright.async_api import async_playwright
        import pyperclip
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                permissions=["clipboard-read", "clipboard-write"],
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(viewer_url)
            max_wait_time = 15
            start_time  = time.time()
            min_text_length = 10000
            pyperclip.copy("")
            while True:
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    print("❌ Timeout: PDF did not finish loading in time.")
                    break

                try:
                    # Check if at least 5 canvas elements exist
                    canvas_count = await page.evaluate("document.querySelectorAll('canvas').length")
                    print(f"🧐 Found {canvas_count} canvas elements so far...")

                    if canvas_count >= 5:
                        print("✅ PDF seems fully loaded!")
                        break

                except Exception as e:
                    print(f"⚠️ Error checking canvas count: {e}")

                # --- Random human-like action ---
                action = random.choice(["scroll", "click", "move"])
                if action == "scroll":
                    delta = random.randint(100, 500)
                    print(f"🖱️ Scrolling down by {delta}px...")
                    await page.mouse.wheel(0, delta)
                elif action == "click":
                    x = random.randint(100, 800)
                    y = random.randint(100, 800)
                    print(f"🖱️ Clicking at ({x}, {y})...")
                    await page.mouse.move(x, y)
                    await page.mouse.click(x, y)
                else:
                    x = random.randint(100, 800)
                    y = random.randint(100, 800)
                    print(f"🖱️ Moving mouse to ({x}, {y})...")
                    await page.mouse.move(x, y)
                    await page.keyboard.down('Control')
                await page.mouse.move(400, 500)
                await page.mouse.click(400, 500)
                await page.keyboard.down('Control')
                await page.keyboard.press('KeyA')
                await page.keyboard.up('Control')

                await page.wait_for_timeout(500)

                await page.keyboard.down('Control')
                await page.keyboard.press('KeyC')
                await page.keyboard.up('Control')

                # Read clipboard
                try:
                    text = pyperclip.paste()
                    text_length = len(text.strip())
                    print(f"📋 Clipboard text length: {text_length}")
                    if text_length >= min_text_length:
                        print(f"✅ Enough text copied ({text_length} characters)!")
                        break
                except Exception as e:
                    print(f"⚠️ Clipboard read error: {e}")
                await asyncio.sleep(random.uniform(0.7, 1.5))

 
            await page.wait_for_timeout(1000)

            # Read clipboard
            text = pyperclip.paste()
            

            await browser.close()

        return viewer_url, text.encode("utf-8") if text.strip() else (viewer_url, None)



    # ──────────────────────────────────────────────────────────────────────────────



    # ──────────────────────────────────────────────────────────────────────────────
    #  4) One public method that chains A → B → C
    #     call this from scrape_pdfs()
    # ──────────────────────────────────────────────────────────────────────────────
    async def fetch_pdf(self, session, url):

        # D) last-resort real browser + pyautogui clipboard (needs your screen/mouse)
        url, data = await self._copy_pdf_text_real_browser_async(url)

        if len(data) >= 10000:
            print(f"✅ Text is long enough and contains 'abstract' and 'references'.")
            return url, data
        else:
            print(f"❌ Fetched text failed validation (length={len(data)}).")
            return url, None
        
if __name__ == "__main__":
    
    urls = ["https://maritime-executive.com/article/infamous-liner-turned-cruise-ship-to-be-sold-at-auction-77-years-after-mv"]
   
    pd.set_option('display.max_columns', None)  # Show al

    f = AsyncHTMLScraper(urls)
    content = asyncio.run(f.scrape())
    df = pd.DataFrame(content, index=None)
    df.to_csv("test.csv")
    print(df)
