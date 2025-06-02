# config.py
import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Or another suitable model
VECTOR_STORE_PATH = "./faiss_store" # Directory to persist FAISS data

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found in environment variables. Please set it in the .env file.")
MONGO_DATABASE_NAME = "maritime_data" # Or whatever your database name is
NEWS_COLLECTION_NAME = "news"
PATENTS_COLLECTION_NAME = "patents"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini model configuration
SMALL_MODEL_NAME = 'gemini-2.5-flash-preview-05-20'
LARGE_MODEL_NAME = 'gemini-2.5-pro-preview-05-06'

# Default model used, "large" model is used for final report generation
GEMINI_MODEL_NAME = SMALL_MODEL_NAME

PDF_OUTPUT_FILENAME = 'analysis_report_langchain.pdf'
RETRIEVER_TOP_K = 50 # How many chunks to retrieve for context for each sub-query

LAST_BUILD_TIMESTAMP_PATH = "./last_build_timestamp.txt" # Path to store the timestamp of the last build

# Check if API key is set
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.")

# Optional email configuration for sending newsletters
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")  # e.g., "smtp.gmail.com"
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))  # Typically 587 for STARTTLS or 465 for SSL
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")  # SMTP login username
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # SMTP login password (consider using an app-specific password)
EMAIL_SENDER = os.getenv("EMAIL_SENDER", EMAIL_USERNAME)  # Defaults to the username if not explicitly set
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS")  # Comma-separated list of recipient addresses 