# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Or another suitable model
VECTOR_STORE_PATH = "./faiss_store" # Directory to persist FAISS data

MONGO_URI = "mongodb+srv://maritime:Marko1324Polo@m0.cslrq4t.mongodb.net/?retryWrites=true&w=majority&appName=M0"
MONGO_DATABASE_NAME = "maritime_data" # Or whatever your database name is
NEWS_COLLECTION_NAME = "news"
PATENTS_COLLECTION_NAME = "patents"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = 'gemini-2.5-flash-preview-04-17' # Or your preferred Gemini model

PDF_OUTPUT_FILENAME = 'analysis_report_langchain.pdf'
RETRIEVER_TOP_K = 25 # How many chunks to retrieve for context for each sub-query

LAST_BUILD_TIMESTAMP_PATH = "./last_build_timestamp.txt" # Path to store the timestamp of the last build

# Check if API key is set
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.") 