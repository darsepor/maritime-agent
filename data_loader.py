# data_loader.py
import pandas as pd # <-- Add import
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import CSV_FILE_PATH, CSV_CONTENT_COLUMN

# Define splitter configuration (can be moved to config.py if preferred)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def split_documents(documents):
    """Splits loaded documents into smaller chunks."""
    if not documents:
        return []
    print(f"Splitting {len(documents)} documents into chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True, # Optional: adds index of chunk's start in original doc
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"Split into {len(split_docs)} chunks.")
    return split_docs

def load_and_chunk_documents():
    """Loads documents from CSV using Pandas, creates Document objects, splits, returns originals and chunks."""
    print(f"Loading raw data from: {CSV_FILE_PATH} using Pandas")

    original_documents_cleaned = []
    chunked_documents = []

    try:
        # Use pandas to read the CSV - it often handles quoting issues better
        df = pd.read_csv(
            CSV_FILE_PATH,
            encoding='utf-8',
            on_bad_lines='warn', # Or 'skip' to ignore problematic rows, 'error' to fail
            encoding_errors='ignore', # Add this line to handle UTF-8 decoding errors
            # You might explore other pandas options like 'escapechar' if needed
        )
        print(f"Loaded {len(df)} rows using Pandas.")

        if df.empty:
            print("Warning: No documents loaded from CSV. Check CSV format and content.")
            return [], []

        # --- Create clean Document objects from DataFrame rows ---
        expected_columns = df.columns.tolist() # Get columns directly from the loaded data

        for i, row in df.iterrows():
            # Explicitly get the page content from the designated column
            content = row.get(CSV_CONTENT_COLUMN, '')

            # Create metadata dict from all *other* columns
            metadata = {}
            for col in expected_columns:
                if col != CSV_CONTENT_COLUMN:
                    # Convert potential non-string types (like NaN) to string or 'N/A'
                    metadata[col] = str(row.get(col, 'N/A')) if pd.notna(row.get(col)) else 'N/A'

            # Add original row number as metadata
            metadata['original_row'] = i

            # Check if content is valid
            if not content or not isinstance(content, str):
                 print(f"Warning: Row {i} has missing or invalid content in '{CSV_CONTENT_COLUMN}'. Skipping.")
                 continue

            # Create the cleaned document
            clean_doc = Document(page_content=content, metadata=metadata)
            original_documents_cleaned.append(clean_doc)
        # --- End document creation ---

        print(f"Processed {len(original_documents_cleaned)} valid documents.")
        if not original_documents_cleaned:
             return [], [] # Return empty lists if no valid docs processed

        # Split the cleaned documents
        chunked_documents = split_documents(original_documents_cleaned)
        return original_documents_cleaned, chunked_documents

    except FileNotFoundError:
        print(f"Error: CSV file not found at {CSV_FILE_PATH}")
        return [], []
    except Exception as e:
        # Catch Pandas-specific errors or general exceptions
        print(f"Error loading or processing CSV with Pandas: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return [], [] # Return empty lists on failure

# Optional: Add text splitting logic here if posts are very long - REMOVED, now integrated above
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# def split_documents(documents, chunk_size=1000, chunk_overlap=200):
#     print(f"Splitting {len(documents)} documents into chunks...")
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
#     split_docs = text_splitter.split_documents(documents)
#     print(f"Split into {len(split_docs)} chunks.")
#     return split_docs 