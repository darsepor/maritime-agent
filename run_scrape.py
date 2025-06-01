
import sys
import os
from scraper.scrape_site.scrapesite import AsyncHTMLScraper
import scraper.scrape_site.fieldrules as field
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper', 'URL_collecting'))
from scraper.URL_collecting.collector import URL_collector
import asyncio
import processor
import data_base
import datetime
from dotenv import load_dotenv
import os
import time
import pandas as pd
from collections import defaultdict
def scrape(domain,start_time, end_time, limit, uri):


      # --- make sure times    are datetime.datetime ---
    if isinstance(start_time, datetime.date) and not isinstance(start_time, datetime.datetime):
        start_time = datetime.datetime.combine(start_time, datetime.datetime.min.time())
    if isinstance(end_time,   datetime.date) and not isinstance(end_time,   datetime.datetime):
        end_time   = datetime.datetime.combine(end_time,   datetime.datetime.min.time())


    domain_source = f"{domain}_urls"

    mongo = data_base.MongoHandler(uri)

    data_= mongo.get_documents(domain_source, {"scraped": False,     "date": {
        "$gte": start_time,
        "$lte": end_time}
        }, limit)        


    urls = [doc["url"] for doc in data_ if "url" in doc]
    print(f"{len(urls)} non-scraped urls loaded from db")
    input("I recommend you to out on vpn. Press enter to start scraping...")
    print("scraping")
    
    
    
    if domain == "studies":
        links = [doc["pdf_link"] for doc in data_ if "pdf_link" in doc]
        session = AsyncHTMLScraper(links)
        session.semaphore = asyncio.Semaphore(1)
        content = asyncio.run(session.scrape_pdfs())

        data = pd.DataFrame(content)

        # HOTFIX:
        
        try:
            lookup = {doc["url"]: {
                "authors": doc.get("authors"),
                "title": doc.get("title"),
                "date": doc.get("date")
            } for doc in data_}

            # Merge
            data["authors"] = data["url"].map(lambda x: lookup.get(x, {}).get("authors"))
            data["title"] = data["url"].map(lambda x: lookup.get(x, {}).get("title"))
            data["date"] = data["url"].map(lambda x: lookup.get(x, {}).get("date"))
            print(data)
        except: 
            pass

    else:
        session = AsyncHTMLScraper(urls)
        data = asyncio.run(session.scrape()) 

    size = len(data)
    return data, size

def enrich_data(data, domain):
    process = processor.ArticleMetadataProcessor()
    print("Got data to process")
    enriched_data = process.enrich_dataframe(data, domain)
    print("data to csv_file")
    return enriched_data

def save_data(data, name,domain):
    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    data.to_parquet(f"{domain}_{name}.parquet", engine='pyarrow', compression='snappy')

def push_data_to_mongo(data, domain, uri):


    domain_source = f"{domain}_urls"

    if domain == "news":
        required_fields = ["url", "date", "text", "scrape_time", "keywords_kongsberg", "keywords_maritime"]
        id= "url" 
    elif domain == "patents":
        required_fields = ["patent_code","url", "priority_date","publication_date", "description", "scrape_time", "keywords_kongsberg", "keywords_maritime"]
        data["url"] = data["url"].str.replace("http://", "https://")
        data["patent_code"] = data["url"].str.extract(r'/patent/([^/]+)')
        id = "patent_code"
    else:
        required_fields = ["url"]
        id= "url"
        for col in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data[col]):
                data = data[data[col].notna()]  # Drop NaT rows
   
        
        
    mongo = data_base.MongoHandler(uri)
    docs = mongo.prepare_documents_from_df(data, field.field_rules_article_basic, id, domain)


    data_ns = mongo.filter_out_scraped_df(domain_source,data, id)   #filter our data that has already been scraped should be none if ulrs to scrape pulled from db with scraped = False

    print("num data after filtering out scraped" ,len(data_ns))
    
    docs = mongo.prepare_documents_from_df(data_ns, required_fields,id ,domain) #Remove rows with missing field and duplicates conver to dict
    print("num data after cleaning", len(docs))
    ids = mongo.insert_many_safe(domain, docs)
    marked = mongo.mark_scraped(domain_source, ids)
    if marked and  marked >0:
        print(f"Marked {marked} urls as scraped")
    


def run_scrape(domain,start_time, end_time, limit, uri):
    # Scraping and saving data locally

    
    data, size = scrape(domain,start_time, end_time, limit,uri)
    print(f"Got {size} data points")
    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    save_data(data,current_time,domain)
    print("A save copy saved in case enrichement fails")
    enriched_data = enrich_data(data, domain)
    print("Enrichment success overwriting original data")
    save_data(enriched_data,current_time, domain)
    print(f"data saved with a name {domain}_{current_time}.parquet")

    #Downloading data and pushin to mongo
    print("Saving to db turn your VPN off!!")
    input("Press enter to continue...")
    try:
        push_data_to_mongo(enriched_data, domain, uri)
    except Exception as e:
        print(f"Error: {e}. Data is saved locally at {domain}_{current_time}.parquet")

def get_urls(uri, start_date=None, end_date=None, patents_day_min=1, news_day_min = 5):


    #check existing urls:
    db = data_base.MongoHandler(uri)
    filter_dates = {
    "date": {
        "$gte": start_date,
        "$lte": end_date
    }
    }
    urls_news = db.get_documents("news_urls", filter=filter_dates, limit = 100000)
    urls_patents = db.get_documents("patents_urls", filter=filter_dates, limit =100000)
    urls_studies = db.get_documents("studies_urls", filter=filter_dates, limit=100000)
    news_caps    = find_caps(urls_news)
    patent_caps  = find_caps(urls_patents)
    return news_caps, patent_caps

def find_caps(
        documents,
        lookback_days: int = 100,        # rolling-mean window
        low_ratio: float = 0.20,         # “under 20 %” threshold
        high_ratio: float = 0.50,        # “over 50 %” threshold
        min_gap_days: int = 10,          # smallest cap you will store
        recovery_high_days: int = 5      # #high days (in last 10) that close a cap
    ):
    """
    Returns [(start_date, end_date), …] for the caps defined as:
      • At least `min_gap_days` in length.
      • Opens after *10 consecutive* low days (< low_ratio * rolling_avg).
      • While open, it keeps extending one day at a time.
      • The moment the **last 10 days** contain ≥ `recovery_high_days`
        with count > high_ratio * rolling_avg,
        the cap is closed **at the day before that 10-day block starts**.
    """

    # ------- 1. daily counts ----------
    counts = defaultdict(int)
    for doc in documents:
        counts[doc["date"].date()] += 1

    if not counts:
        return []

    df = (pd.DataFrame(sorted(counts.items()), columns=["date", "count"])
            .set_index("date")
            .asfreq("D", fill_value=0))

    # rolling mean of the previous `lookback_days` (inclusive)
    df["avg"] = df["count"].rolling(window=lookback_days, min_periods=1).mean()

    low_mask  = df["count"] <  low_ratio  * df["avg"]   # candidate-opening days
    high_mask = df["count"] >  high_ratio * df["avg"]   # recovery test

    dates = df.index.to_list()
    n     = len(dates)

    caps  = []
    state = "idle"          # “idle” | “cap”
    cap_start_idx = None
    consecutive_low = 0

    i = 0
    while i < n:
        if state == "idle":
            if low_mask[i]:
                consecutive_low += 1
                if consecutive_low == 10:           # 10 straight lows ⇒ open cap
                    cap_start_idx   = i - 9         # first of those 10 days
                    state           = "cap"
                    # we already have the first 10-day window in hand
            else:
                consecutive_low = 0
            i += 1
        else:                                       # -------- inside an open cap ----------
            # Have we accumulated ≥10 days since the cap opened?
            window_end = i
            window_start = i - 9
            if window_start >= cap_start_idx:       # we have a full 10-day window
                high_days = high_mask[window_start:window_end + 1].sum()
                if high_days >= recovery_high_days:
                    # close the cap at the day before window_start
                    cap_end_idx   = window_start - 1
                    if cap_end_idx - cap_start_idx + 1 >= min_gap_days:
                        caps.append((dates[cap_start_idx], dates[cap_end_idx]))
                    # reset everything and CONTINUE scanning from window_start
                    state = "idle"
                    consecutive_low = 0
                    i = window_start        # ← don’t lose the day we’re on
                    continue
            # keep extending the cap
            i += 1

    # reached the end while still in a cap → store it
    if state == "cap":
        if n - cap_start_idx >= min_gap_days:
            caps.append((dates[cap_start_idx], dates[-1]))

    return caps


def scrape_timerange(uri,start_date=None,end_date=None, limit = 1):
    get_recent = not (start_date and end_date)
    
    
    if not (start_date and end_date):
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=30)
        end_date = today
    news_frames   = []   # collectors for per-range DataFrames
    patent_frames = []
    if get_recent:
        collector = URL_collector(start_date, end_date, limit)
        input("Scraping recent URLS put on VPN:")
        collector.get_recent()
        news_frames.append(collector.news_data)
        patent_frames.append(collector.patent_data)
        
    else:
        news_caps, patents_caps = get_urls(uri,start_date,end_date) # get caps in news and patents
        print(news_caps,patents_caps)
        input("scrape urls put on vpn, enter to continue:")


        #scrape news urls
        for cap_start, cap_end in news_caps:
            collector = URL_collector(cap_start, cap_end, limit)
            collector.get_urls_from_marine_link()
            
            news_frames.append(collector.news_data)

        #scrape patents urls
        for cap_start, cap_end in patents_caps:
            collector = URL_collector(cap_start, cap_end, limit)
            collector.get_google_patents()
            patent_frames.append(collector.news_data)
        

    input("We updated the existing urls put off vpn to uplaod to db:")
    #push these urls to database
    db = data_base.MongoHandler(uri)


    if news_frames:
        news_df = pd.concat(news_frames, ignore_index=True)
        news_clean = db.prepare_documents_from_df(
            news_df, ["url","date","scraped","domain"], domain="news"
        )
        db.insert_many_safe("news", news_clean)

    if patent_frames:
        patent_df = pd.concat(patent_frames, ignore_index=True)
        patents_clean = db.prepare_documents_from_df(
            patent_df, ["url","priority_date","scraped","domain"], domain="patents"
        )
        db.insert_many_safe("patents", patents_clean)
    #Finally update our database
    total = limit*((end_date-start_date).days)
    print(f"total is {total}")
    run_scrape("news",start_date,end_date, limit = total, uri=uri)
    run_scrape("patents", start_date,end_date, limit = total, uri=uri)



#Define variables to run
#domain = "studies"
#start_time = datetime(2020, 1, 1)
#end_time = datetime(2023, 5, 23)
#limit = 200



load_dotenv()
uri = os.getenv("MONGO_URI")
print(uri)
scrape_timerange(uri)
#run_scrape(domain,start_time, end_time, limit, uri)

