from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
import pandas as pd
import time
from datetime import datetime
import asyncio
import processor
import numpy as np


class MongoHandler:
    def __init__(self, uri, db_name="maritime_data"):
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.collections = {
            "news": self.db["news"],
            "patents": self.db["patents"],
            "patents_urls": self.db["patents_urls"],
            "news_urls": self.db["news_urls"]

        }

    def insert_one_safe(self, domain, doc):
        collection = self.collections.get(domain)
        if not collection or "_id" not in doc:
            return False
        try:
            collection.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    def get_unscraped(self, domain, limit=100):
        collection = self.collections.get(domain)
        if collection is None:
            return []
        return list(collection.find({"scraped": False}).limit(limit))
    def count_documents(self, domain, filter=None):
        collection = self.collections.get(domain)
        if collection is None:
            return 0
        filter = filter or {}
        return collection.count_documents(filter)


    def get_documents(self, domain, filter=None, limit=100):
        collection = self.collections.get(domain)
        if collection is None:
            return []
        filter = filter or {}  # default to no filter
        return list(collection.find(filter).limit(limit))
    def mark_scraped(self, domain, ids):
        collection = self.collections.get(domain)
        if collection is None or not ids:
            print("No collection or ids provided. SCRAPE STATUS NOT UPDATED")
            return 0
        # Only update those where scraped != True (or doesn't exist)
        result = collection.update_many(
            {"_id": {"$in": ids}, "scraped": {"$ne": True}},
            {"$set": {"scraped": True}}
        )
        return result.modified_count
    
    def insert_many_safe(self, domain_input, docs):
        
        domain = self.check_domain_by_fields(domain_input, docs)
        collection = self.collections.get(domain)
        
        if collection is None or not docs:
            print("No collection or documents provided")
            return 0
        
        # Extract all _id values
        ids = [doc["_id"] for doc in docs if "_id" in doc]
        existing_ids = set(doc["_id"] for doc in collection.find({"_id": {"$in": ids}}, {"_id": 1}))
        print(len(existing_ids))
        # Filter out duplicates
        new_docs = [doc for doc in docs if doc["_id"] not in existing_ids]
        inserted_ids = [doc["_id"] for doc in new_docs]
        print(len(inserted_ids))
        # Insert remaining new documents
        if new_docs:
            try:
                collection.insert_many(new_docs, ordered=False)
                print(f"✅ Inserted {len(inserted_ids)} new documents into MongoDB.")
                return inserted_ids
            except Exception as e:
                print(f"Error inserting documents: {e}")
                return 0
        return 0
    def prepare_documents_from_df(self, df, required_fields, id_field="url", domain= "news"):
        # Drop rows missing any required fields and duplicates and create an id-field
        try:
            filtered_df = df.dropna(subset=required_fields)
            filtered_df = filtered_df.drop_duplicates(subset=[id_field])
            filtered_df["_id"] = filtered_df[id_field] #create an id-field
            try:
                date = "date" if domain == "news" else "priority_date"

                filtered_df["date"] = pd.to_datetime(filtered_df[date])
            except Exception as e:
                
                print(f"Could not convert date to datetime: {e}")
        except Exception as e:
            print(f"Error: {e}")
            return []
        for col in filtered_df.columns:
            if filtered_df[col].apply(lambda x: isinstance(x, np.ndarray)).any():
                filtered_df[col] = filtered_df[col].apply(lambda x: x.tolist() if isinstance(x, np.ndarray) else x)
        documents = filtered_df.to_dict(orient="records") # Convert to list of dictionaries
        return documents
    

    def filter_out_scraped_df(self, domain, df, id_field="url"):
        #Filter out data that has already been scraped based on the info in database
        collection = self.collections.get(domain)
        if collection is None:
            return df  # return original if no filtering can be done
        df["_id"] = df[id_field]
        input_ids = df[id_field].tolist()

        # Find which IDs are already scraped
        scraped_ids = set(
            doc["_id"] for doc in collection.find(
                {"_id": {"$in": input_ids}, "scraped": True},
                {"_id": 1}
            )
        )

        # Filter out scraped rows
        return df[~df[id_field].isin(scraped_ids)]
    def check_domain_by_fields(self, domain, docs):
        domain_works = False
        while not domain_works:
            # Define expected fields for each domain
            domain_field_map = {
                "news": {"url","title","date","text","image","scrape_time","keywords_kongsberg","keywords_maritime"},
                "patents": {'abstract', 'claims', 'publication_date', 'cited_by', 'approx_expiration', 'citations', 'status', 'priority_date', '_id', 'keywords_kongsberg', 'description', 'scrape_time', 'date', 'title', 'url', 'keywords_maritime', 'keywords_kongsberg'},
                "scientific_articles": {"url", "title", "date", "scraped", "doi"},
                "blogs": {"url", "title", "date", "scraped"},
                "social_media": {"url", "content", "date", "scraped", "platform"},
                "news_urls": {"_id","headline","date", "url", "domain", "scraped"}, 
                "patents_urls": {"_id","patent_code","priority_date","url", "domain", "scraped"},
            }

            # Extract actual fields from the first document
            doc_fields = set(docs[0].keys())
            expected_fields = domain_field_map.get(domain)

            if expected_fields is None:
                print(f"⚠️ Unknown domain '{domain}'. Known domains: {', '.join(domain_field_map.keys())}")
            elif expected_fields != doc_fields:
                print(f"⚠️ Field mismatch for domain '{domain}':")
                print(f"    Expected fields: {expected_fields}")
                print(f"    Found fields:    {doc_fields}")
            else:
                return domain  # All good

            # Prompt user
            new_domain = input("Enter a valid domain to use:").strip()
            domain = new_domain
        return new_domain if new_domain else domain
    
    def update_scraped(self, domain):
        print(f"🔍 Fetching _ids from domain '{domain}'...")
        docs = self.get_documents(domain, filter={}, limit=10**6)
        ids = [doc["_id"] for doc in docs if "_id" in doc]
        print(len(ids))
        
        if not ids:
            print("⚠️ No documents found or missing _id fields.")
            return 0

        urls_collection = f"{domain}_urls"
        updated_count = self.mark_scraped(urls_collection, ids)
        print(f"✅ Marked {updated_count} entries in '{urls_collection}' as scraped.")
        return updated_count


if __name__ == "__main__":
    data = pd.read_csv("news_2005-01-01_2015-01-01.csv")
    
    print(len(data))
    db = MongoHandler("mongodb+srv://maritime:Marko1324Polo@m0.cslrq4t.mongodb.net/?retryWrites=true&w=majority&appName=M0")
    data =db.filter_out_scraped_df("news_urls", data, "url")
    print(len(data))
    docs = db.prepare_documents_from_df(data, ["url", "headline", "date", "domain", "scraped"], "url", "news")
    db.insert_many_safe("news", docs)
    
    
