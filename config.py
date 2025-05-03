# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

CSV_FILE_PATH = 'blog_posts.csv'
CSV_CONTENT_COLUMN = 'text' # Column with the main text to embed
CSV_METADATA_COLUMNS = ['title', 'date'] # Columns to store as metadata

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Or another suitable model
VECTOR_STORE_PATH = "./chroma_db_store" # Directory to persist ChromaDB data

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = 'gemini-2.5-flash-preview-04-17' # Or your preferred Gemini model

PDF_OUTPUT_FILENAME = 'analysis_report_langchain.pdf'
RETRIEVER_TOP_K = 6 # How many chunks to retrieve for context

# Check if API key is set
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.") 