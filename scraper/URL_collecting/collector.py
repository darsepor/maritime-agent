import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup  # needed for google as they have dynamical rendering so otherwise you get just skeleton
import time
from patent_helper import *
import random
import re

from selenium import webdriver #again for google for rendering elements
from selenium.webdriver.chrome.options import Options  #again for google for rendering elements
import asyncio # for asynchronous execution to speed up scraping calls
import sys
import os 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'../')))
from scrape_site.scrapesite import AsyncHTMLScraper


class URL_collector:
    def __init__(self, start_date, end_date, urls_per_day):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.urls_per_day = min(urls_per_day,1000)  # to ensure that we increment day at least by 1 see "timeframe_days = int(max_urls / self.urls_per_day)"

        # DataFrames to store retrieved URLs and metadata
        self.patent_data = pd.DataFrame(columns=["patent_code", "priority_date", "url", "domain", "scraped"])
        self.news_data = pd.DataFrame(columns=["headline", "date", "url", "domain", "scraped"])
        self.science_data = pd.DataFrame(columns=["title", "date", "url"])

        # DataFrames to store retrieval stats
        date_range = pd.date_range(start=self.start_date, end=self.end_date)
        self.patent_retrieval = pd.DataFrame({
            "date": date_range,
            "proportion_retrieved": 0.0
        }).set_index("date")

    def get_urls_from_marine_link(self):
        # Field extraction rule for archive page
        field_rules = {
            "articles": lambda tree: [
                {
                    "headline": a.css_first("h3").text(strip=True),
                    "date": a.css_first("div.date").text(strip=True),
                    "url": "https://www.marinelink.com" + a.attributes.get("href", "")
                }
                for a in tree.css("a[href^='/news/']")
                if a.css_first("h3") and a.css_first("div.date")
            ]
        }

        monthly_roots = [
            f"https://www.marinelink.com/archive/{date.strftime('%Y%m')}"
            for date in pd.date_range(self.start_date, self.end_date, freq="MS")
        ]
        print(f"passing montly roots {monthly_roots}")
        # Scrape and flatten
        scraper = AsyncHTMLScraper(monthly_roots, field_rules)
        raw_results = asyncio.run(scraper.scrape_paginated_archives(monthly_roots))
        self.news_data = pd.concat([
            self.news_data,
            self._flatten_news_results(raw_results, "marinelink.com")
        ], ignore_index=True)

    def get_urls_from_any_website_defaul(self,urls):
        field_rules = 0
        scraper = AsyncHTMLScraper(urls, field_rules)
        result = asyncio.run(scraper.scrape())
        

    def get_google_patents(self, search_term="maritime"):
        field_map = {
            "url": lambda item: (
                "https://patents.google.com/" + item.find("state-modifier", attrs={"data-result": True})['data-result']
                if item.find("state-modifier", attrs={"data-result": True}) else None
            ),
            "patent_code": lambda item: (
                re.search(r'patent/([^/]+)', item.find("state-modifier", attrs={"data-result": True})['data-result']).group(1)
                if item.find("state-modifier", attrs={"data-result": True}) else None
            ),
            "priority_date": lambda item: (
                re.search(r'Priority\s+(\d{4}-\d{2}-\d{2})',
                        item.find("h4", class_="dates style-scope search-result-item").get_text()).group(1)
                if item.find("h4", class_="dates style-scope search-result-item") else None
            )
        }

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)

        current_date = self.start_date
        next_date = current_date
        max_urls = 1000
            
        timeframe_days = int(max_urls / self.urls_per_day)
        while next_date < self.end_date:
            
            next_date = min(current_date + timedelta(days=timeframe_days), self.end_date)

            collected = []
            url = (
                f"https://patents.google.com/?q=({search_term})"
                f"&before=priority:{next_date.strftime('%Y%m%d')}"
                f"&after=priority:{current_date.strftime('%Y%m%d')}"
                f"&num=100&page=0"
            )

            html = get_rendered_html(url, driver)
            

            soup = BeautifulSoup(html, "html.parser")
            total_results = extract_total_results_google(html)
            
        
            if not total_results:
                print(f"[WARN] Could not find total result count at {url}")
                total_results = 0
            if total_results > max_urls:
                timeframe_days = int(max_urls / self.urls_per_day)
                next_date = min(current_date + timedelta(days=timeframe_days), self.end_date)
                
            while int(total_results*2) < max_urls and next_date < self.end_date:
                print("Increasing the number of total results", total_results)
                timeframe_days = int(timeframe_days *2)
                extended = min(next_date + timedelta(days=timeframe_days), self.end_date)
                check_url = (
                    f"https://patents.google.com/?q=({search_term})"
                    f"&before=priority:{extended.strftime('%Y%m%d')}"
                    f"&after=priority:{current_date.strftime('%Y%m%d')}"
                    f"&num=100&page=0"
                )
                check_html = get_rendered_html(check_url, driver)
                check_results = extract_total_results_google(check_html)
                
                if  check_results < max_urls:
                    total_results = check_results
                    next_date = extended
                else:
                    break
                
            print("TOTAL RESULTS", total_results)
            range_max = min(int(total_results / 100),9)
            for page in range(range_max + 1):
                print(f"Time frame {current_date} to {next_date}, Page number, {page}")
                page_url = (
                    f"https://patents.google.com/?q=({search_term})"
                    f"&before=priority:{next_date.strftime('%Y%m%d')}"
                    f"&after=priority:{current_date.strftime('%Y%m%d')}"
                    f"&num=100&page={page}"
                )
                print(page_url)
                print(time.sleep(0.7))
                html = get_rendered_html(page_url, driver)
                soup = BeautifulSoup(html, "html.parser")

                page_results = extract_urls(soup, field_map)


                if not page_results:
                    break
                else:
                    print(f"[✓] Page {page} scraped: {page_url}")
                    print(len(page_results))
                
                    

                collected.extend(page_results)
                time.sleep(random.uniform(0.2, 0.6))
                if len(page_results)< 95:
                    break
            for item in collected:
                item["domain"] = "patents.google.com"
                item["scraped"] = False
            self.patent_data = pd.concat([self.patent_data, pd.DataFrame(collected)], ignore_index=True)
            num_returned = len(collected)
            prop_retrieved = num_returned / total_results if total_results else 0
            
            for day in pd.date_range(current_date, next_date):  
                self.patent_retrieval.at[day, "proportion_retrieved"] = prop_retrieved
            print(f"Retrieved {num_returned} patents from {current_date} to {next_date}")

            time.sleep(0.5)
            current_date = next_date
            

        driver.quit()






    def _flatten_news_results(self, results, domain):
        
        rows = []
        for result in results:
            for article in result.get("articles", []):
                date = pd.to_datetime(article.get("date"), errors="coerce")
                if pd.notna(date) and self.start_date <= date <= self.end_date:
                    rows.append({
                        "headline": article["headline"],
                        "date": date.strftime("%Y-%m-%d"),
                        "url": article["url"],
                        "domain": domain,
                        "scraped": False
                    })

        return pd.DataFrame(rows)


if __name__ == "__main__":






    # Define your collections
    start_date = "1825-01-01"
    end_date = "2025-5-22"
    collector = URL_collector(start_date, end_date, urls_per_day=1)
    collector.get_google_patents('''(kongsberg OR autonomous OR sonar OR maritime OR navigation OR missile OR "remote sensing" OR "propulsion system" OR "underwater vehicle" OR "fire control system" OR radar OR "combat system")''')
    path = f"patents_{start_date}_{end_date}.csv"
    collector.patent_data["url"] = collector.patent_data["url"].str.replace(r"/[^/]+$", "/en", regex=True)
    collector.patent_data.to_csv(path, index=False)


    # Clean and prepare records


    
    