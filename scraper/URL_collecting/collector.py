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
import sources
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'../')))
from scrape_site.scrapesite import AsyncHTMLScraper
from urllib.parse import quote_plus


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
        scraper = AsyncHTMLScraper(monthly_roots, field_rules, apply_domain_rules=False)
        raw_results = asyncio.run(scraper.scrape_paginated_archives(monthly_roots))
        self.news_data = pd.concat([
            self.news_data,
            self._flatten_news_results(raw_results, "marinelink.com")
        ], ignore_index=True)


    def get_recent(self):
        self.get_recent_news_simple()
        self.get_google_patents()
        self.get_urls_from_marine_link()


    def get_recent_news_simple(self):
        domains = sources.domains
        print(domains)
        for dom in domains:
            rules = sources.DOMAIN_RULES_URL[dom]
            categories = rules["categories"]
            urls = []
            if categories:
                for cat in categories:
                    urls.append(f"{rules['url_base']}/{cat}")
            else: urls.append(rules['url_base'])

            
            scraper = AsyncHTMLScraper(urls, rules["field_rules"], apply_domain_rules=False, get_urls=True)
            scraper.semaphore = asyncio.Semaphore(1)
            raw_results = asyncio.run(scraper.scrape())
            
            
            print("GOT raw result", len(raw_results))


            self.news_data = pd.concat([
                self.news_data,
                self._flatten_news_results(raw_results, dom)
            ], ignore_index=True)
 

    
    def get_google_scholar(self, search_term = "maritime"):


        field_map = {
            "title": lambda item: (
                item.select_one("h3.gs_rt a").text.strip()
                if item.select_one("h3.gs_rt a") else None
            ),
            "url": lambda item: (
                item.select_one("h3.gs_rt a")["href"]
                if item.select_one("h3.gs_rt a") and item.select_one("h3.gs_rt a").has_attr("href") else None
            ),
            "authors": lambda item: (
                item.select_one(".gs_a").text.strip()
                if item.select_one(".gs_a") else None
            ),
            "date": lambda item: (
                extract_year(item.select_one(".gs_a").text)
                if item.select_one(".gs_a") else None
            ),
            "pdf_link": lambda item: (
                item.select_one(".gs_or_ggsm a")["href"]
                if item.select_one(".gs_or_ggsm a") and item.select_one(".gs_or_ggsm a").has_attr("href") else None
            ),
            "snippet": lambda item: (
                item.select_one(".gs_rs").text.strip()
                if item.select_one(".gs_rs") else None
            )
        }

       

        def extract_year(text):
            return None
        

        QUERY = "marine propulsion"    # no quotes
        NUM_PAGES = 20               # how many pages
        SORT_BY_DATE = False            # True = sort by date, False = sort by relevance

        base_url = "https://scholar.google.com/scholar"
        sort_flag = "1" if SORT_BY_DATE else "0"



        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        year_low = self.start_date.year
        year_high = self.end_date.year
        for year in range(year_low,year_high+1):
            time.sleep(random.uniform(4,12))
            collected = []
            for i in range(NUM_PAGES):
                time.sleep(random.uniform(0.05,0.1))
                start = i * 10
                query_string = f"hl=fi&as_sdt=0%2C5&q={quote_plus(QUERY)}&btnG="
                if SORT_BY_DATE:
                    query_string += f"&scisbd={sort_flag}"
                if start > 0:
                    query_string += f"&start={start}"
                query_string  += f"&as_ylo={year}&as_yhi={year}"
                url = f"{base_url}?{query_string}"
                
                try:
                    html = get_rendered_html(url, driver)
                    soup = BeautifulSoup(html, "html.parser")
                    data = extract_urls(soup,field_map, domain="scholar")
                    if not data:
                        break
      
                    print(f"[✓] Page {i + 1} scraped: {url}")
                    print(f"Number of results: {len(data)}")
                    year_date = f"{year}-01-01"
                    for result in data:
                        if result.get("date") is None:
                            result["date"] = year_date
                    collected.extend(data)
                    time.sleep(random.uniform(0.2, 0.65))  # Sleep to be polite

                except:
                    print(f"skipping link {query_string}")
            for item in collected:
                item["domain"] = "scholar.google.com"
                item["scraped"] = False

            # Append to self.science_data
            if collected:
                year_df = pd.DataFrame(collected)
                self.science_data = pd.concat([self.science_data, year_df], ignore_index=True)

                






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

                #Ensure we have some date-value
                midpoint_date = (current_date + (next_date - current_date) / 2).strftime('%Y-%m-%d')
                for result in page_results:
                    if result.get("priority_date") is None:
                        result["priority_date"] = midpoint_date
                                    

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
        print(results)
        for result in results:
            for article in result.get("articles", []):
                
                raw_date = article.get("date")

                date = parse_mixed_date(raw_date)
                if pd.notna(date) and self.start_date <= date <= self.end_date:
                    rows.append({
                        "headline": article["headline"],
                        "date": date.strftime("%Y-%m-%d"),
                        "url": article["url"],
                        "domain": domain,
                        "scraped": False
                    })
                else:
                    pass
            
        return pd.DataFrame(rows)


if __name__ == "__main__":

    
    


    collector = URL_collector("2000-01-01", "2021-12-01", urls_per_day=5)

    collector.get_google_scholar()
    data = collector.science_data
    data.to_csv("sciense_data.csv")

    #collector.get_recent_news()
    #urls = collector.news_data
    #print(urls)
    #urls.to_csv("test.csv")

    # Define your collections
    start_date = "1995-01-01"
    end_date = "2025-12-12"
    #collector = URL_collector(start_date, end_date, urls_per_day=5)
    #collector.get_google_patents()
    #path = f"news_{start_date}_{end_date}.csv"
    #
    #collector.news_data.to_csv(path, index=False)



    
    
