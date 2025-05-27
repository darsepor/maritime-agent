from scraper.scrape_site.scrapesite import AsyncHTMLScraper
import scraper.scrape_site.fieldrules as field
import asyncio
import processor
import data_base
from datetime import datetime
from dotenv import load_dotenv
import os
import time

def scrape(domain,start_time, end_time, limit, uri):
    domain_source = f"{domain}_urls"

    mongo = data_base.MongoHandler(uri)

    data= mongo.get_documents(domain_source, {"scraped": False,     "date": {
        "$gte": start_time,
        "$lte": end_time}
        }, limit)        
    urls = [doc["url"] for doc in data if "url" in doc]
    print(f"{len(urls)} non-scraped urls loaded from db")
    input("I recommend you to out on vpn. Press enter to start scraping...")
    print("scraping")
    
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

def save_data(data, name):
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
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
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    save_data(data,current_time)
    print("A save copy saved in case enrichement fails")
    enriched_data = enrich_data(data, domain)
    print("Enrichment success overwriting original data")
    save_data(enriched_data,current_time)
    print(f"data saved with a name {domain}_{current_time}.parquet")

    #Downloading data and pushin to mongo
    print("Saving to db turn your VPN off!!")
    input("Press enter to continue...")
    try:
        push_data_to_mongo(enriched_data, domain, uri)
    except Exception as e:
        print(f"Error: {e}. Data is saved locally at {domain}_{current_time}.parquet")



#Define variables to run
domain = "news"
start_time = datetime(2000, 1, 1)
end_time = datetime(2020, 5, 23)
limit = 8000



load_dotenv()
uri = os.getenv("MONGO_URI")
print(uri)

run_scrape(domain,start_time, end_time, limit, uri)

