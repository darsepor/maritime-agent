from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
import pandas as pd
import time
from datetime import datetime
import asyncio
import processor
import numpy as np
from bson.objectid import ObjectId
from dateutil import parser as date_parser
import os
from dotenv import load_dotenv


class MongoHandler:
    def __init__(self, uri, db_name="maritime_data"):
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[db_name]
        self.collections = {
            "news": self.db["news"],
            "patents": self.db["patents"],
            "patents_urls": self.db["patents_urls"],
            "news_urls": self.db["news_urls"],
            "studies": self.db["studies"],
            "studies_urls": self.db["studies_urls"]

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
                date = "date" if domain == "news" or "studies" else "priority_date"

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
                "news": {"_id","url","title","date","text","image","scrape_time","keywords_kongsberg","keywords_maritime"},
                "patents": {'citations', 'approx_expiration', 'abstract', 'patent_code', 'date', 'similar_documents', 'keywords_maritime', 'scrape_time', '_id', 'title', 'application_granted', 'url', 'description', 'keywords_kongsberg', 'cited_by', 'publication_date', 'claims', 'status', 'priority_date'},
                "blogs": {"url", "title", "date", "scraped"},
                "social_media": {"url", "content", "date", "scraped", "platform"},
                "news_urls": {"_id","headline","date", "url", "domain", "scraped"}, 
                "patents_urls": {"_id","patent_code","priority_date","url", "domain", "scraped"},
                "studies_urls": {"_id","title","date","url","authors","pdf_link","snippet","domain", "scraped"},
                "studies": {"_id","title","date","url","authors","text","abstract","references","conclusion"}
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

    def count_news_for_vectorization(self, since_timestamp=None):
        """Counts news documents, optionally filtered by since_timestamp based on 'scrape_time'."""
        collection = self.collections.get("news")
        if collection is None:
            return 0
        
        query = {}
        if since_timestamp:
            try:
                since_dt = date_parser.isoparse(since_timestamp) if isinstance(since_timestamp, str) else since_timestamp
                query["scrape_time"] = {"$gt": since_dt}
            except Exception as e:
                print(f"Warning: Could not parse since_timestamp for counting news: {since_timestamp}. Error: {e}.")
                # Decide if you want to count all or return 0/raise error
        
        return collection.count_documents(query)

    def get_news_for_vectorization(self, limit=0, skip=0, since_timestamp=None):
        """Fetches news documents for vectorization, returning _id and text.
           Optionally fetches documents newer than since_timestamp based on 'scrape_time'."""
        collection = self.collections.get("news")
        if collection is None:
            return []
        
        query = {}
        if since_timestamp:
            try:
                # Ensure since_timestamp is a datetime object for comparison
                # Assuming scrape_time in DB is also a datetime object or ISODate string
                since_dt = date_parser.isoparse(since_timestamp) if isinstance(since_timestamp, str) else since_timestamp
                query["scrape_time"] = {"$gt": since_dt}
                print(f"Fetching news with scrape_time > {since_dt}")
            except Exception as e:
                print(f"Warning: Could not parse since_timestamp for news: {since_timestamp}. Error: {e}. Fetching all news.")

        projection = {"_id": 1, "text": 1, "title":1, "date":1, "url":1, "scrape_time": 1, "keywords_maritime":1, "keywords_kongsberg":1}
        
        cursor = collection.find(query, projection)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
            
        return list(cursor)

    def get_patents_for_vectorization(self, limit=0, skip=0, since_timestamp=None):
        """Fetches patent documents for vectorization, returning _id and concatenated text fields.
           Optionally fetches documents newer than since_timestamp based on 'scrape_time'."""
        collection = self.collections.get("patents")
        if collection is None:
            return []

        query = {}
        if since_timestamp:
            try:
                since_dt = date_parser.isoparse(since_timestamp) if isinstance(since_timestamp, str) else since_timestamp
                query["scrape_time"] = {"$gt": since_dt}
                print(f"Fetching patents with scrape_time > {since_dt}")
            except Exception as e:
                print(f"Warning: Could not parse since_timestamp for patents: {since_timestamp}. Error: {e}. Fetching all patents.")

        projection = {"_id": 1, "abstract": 1, "claims": 1, "description": 1, "title":1, "date":1, "url":1, "patent_code":1, "scrape_time": 1, "keywords_maritime":1, "keywords_kongsberg":1}
        
        cursor = collection.find(query, projection)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        
        patents_data = []
        for doc in cursor:
            abstract_text = doc.get("abstract")
            claims_text = doc.get("claims")
            description_text = doc.get("description")
            text_parts = [
                str(abstract_text) if abstract_text is not None else "",
                str(claims_text) if claims_text is not None else "",
                str(description_text) if description_text is not None else ""
            ]
            concatenated_text = " \n\n ".join(part for part in text_parts if part)
            
            # Preserve all projected fields in the returned dict
            patent_item = {k: doc.get(k) for k in projection.keys() if k != "abstract" and k != "claims" and k != "description"}
            patent_item["text"] = concatenated_text
            patents_data.append(patent_item)
        return patents_data

    def count_patents_for_vectorization(self, since_timestamp=None):
        """Counts patent documents, optionally filtered by since_timestamp based on 'scrape_time'."""
        collection = self.collections.get("patents")
        if collection is None:
            return 0

        query = {}
        if since_timestamp:
            try:
                since_dt = date_parser.isoparse(since_timestamp) if isinstance(since_timestamp, str) else since_timestamp
                query["scrape_time"] = {"$gt": since_dt}
            except Exception as e:
                print(f"Warning: Could not parse since_timestamp for counting patents: {since_timestamp}. Error: {e}.")

        return collection.count_documents(query)

    def get_document_by_id(self, domain: str, doc_id: str):
        """Fetches a single document by its MongoDB _id."""
        collection = self.collections.get(domain)
        if collection is None:
            print(f"Warning: Collection for domain '{domain}' not found.")
            return None
        
        # _id in this project is sometimes an ObjectId (Mongo-generated) and
        # sometimes a URL / patent_code string that we set ourselves.  Try both
        # lookup strategies instead of failing immediately.

        query = {"_id": doc_id}
        doc = collection.find_one(query)

        # If that didn't work and the id *could* be an ObjectId, try again.
        if doc is None:
            try:
                object_id = ObjectId(doc_id)
                doc = collection.find_one({"_id": object_id})
            except Exception:
                # not a valid ObjectId string – ignore
                pass

        if doc and "text" not in doc:  # For patents, reconstruct text if not directly stored
            if domain == "patents" and not doc.get("text"):
                text_parts = [
                    doc.get("abstract", ""), 
                    doc.get("claims", ""), 
                    doc.get("description", "")
                ]
                doc["text"] = " \n\n ".join(filter(None, text_parts))
        return doc

if __name__ == "__main__":


    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("Set MONGO_URI in your .env before running this demo script.")

    csv_path = "sciense_data.csv"
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"{csv_path} not found. Provide the dataset before running.")

    db = MongoHandler(mongo_uri)
    df = pd.read_csv(csv_path)
    docs = db.prepare_documents_from_df(df, ["title", "date", "url", "pdf_link", "domain", "scraped"], domain="studies")
    db.insert_many_safe("studies_urls", docs)


    
    
