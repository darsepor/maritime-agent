from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from contextlib import contextmanager
import re
import pandas as pd
from datetime import datetime
import time



def parse_mixed_date(date_str):
    if not date_str:
        return pd.NaT

    date_str = date_str.strip()

    # Try standard ISO first (YYYY-MM-DD)
    try:
        return pd.to_datetime(date_str, format="%Y-%m-%d")
    except ValueError:
        pass

    # Try month abbreviation with dot (e.g. "Nov. 28, 2006")
    try:
        clean = date_str.replace(".", "")  # remove dot from month
        return datetime.strptime(clean, "%b %d, %Y")
    except ValueError:
        pass

    # Try general automatic parsing as fallback
    try:
        return pd.to_datetime(date_str, errors="coerce")
    except Exception:
        return pd.NaT

def get_rendered_html(url, driver=None):
    close_driver = False

    if driver is None:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(options=options)
        close_driver = True

    try:
        print("This is the url", url)
        driver.get(url)

        # Detect based on URL
        if "patents.google.com" in url:
            # Google Patents wait condition
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "search-result-item"))
            )
            
        elif "scholar.google.com" in url:
            print("wating for scholar")
            # Google Scholar wait condition
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.gs_r.gs_or.gs_scl"))
            )
            
            

        else:
            # Default: just a basic wait to let the page load a bit
            WebDriverWait(driver, 5)

        html = driver.page_source
        print(f"Fetched HTML length: {len(html)}")
    except Exception as e:
        print(f"[ERROR] {e} Timeout or failure on: {url}")
        html = driver.page_source
    finally:
        if close_driver:
            driver.quit()

    return html

def extract_total_results_google(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    count_div = soup.find("div", id="count")
    if not count_div:
        return 0

    text = count_div.get_text(strip=True).replace('\xa0', '').replace(',', '')
    
    # Match number that comes just before the word "results"
    match = re.search(r'(\d+)\s*results', text)
    if match:
        return int(match.group(1))
    
    return 0


def extract_urls(soup_or_html, field_map, domain = "google_patents"):
    if isinstance(soup_or_html, str):
        soup = BeautifulSoup(soup_or_html, "html.parser")
    else:
        soup = soup_or_html  # Already parsed

    results = []

    # Restrict to only actual <search-result-item> tags
    if domain == "scholar":
        items = soup.find_all("div", class_="gs_r gs_or gs_scl")
    else:
        items = soup.find_all("search-result-item")

    
    for item in items:
        result = {}
        for field, extractor in field_map.items():
            try:
                result[field] = extractor(item)
            except Exception as e:
                result[field] = None
        results.append(result)

    return results








