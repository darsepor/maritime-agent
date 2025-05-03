# data_loader.py
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document # Import Document base class
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
    """Loads documents from CSV, ensures clean page_content, splits, returns originals and chunks."""
    print(f"Loading raw data from: {CSV_FILE_PATH}")

    # Define ALL columns you want to load from the CSV header
    # Ensure these names match your CSV header exactly
    EXPECTED_CSV_COLUMNS = ['title', 'text', 'keywords', 'segment', 'date', 'url']

    loader = CSVLoader(
        file_path=CSV_FILE_PATH,
        # Load all expected columns into metadata initially
        metadata_columns=EXPECTED_CSV_COLUMNS,
        encoding='utf-8',
        csv_args={'delimiter': ',', 'quotechar': '"'}
    )

    original_documents_cleaned = []
    chunked_documents = []

    try:
        raw_loaded_docs = loader.load()
        print(f"Loaded {len(raw_loaded_docs)} raw rows.")
        if not raw_loaded_docs:
            print("Warning: No documents loaded from CSV. Check CSV format and content.")
            return [], []

        # --- Manually create clean Document objects --- 
        for i, raw_doc in enumerate(raw_loaded_docs):
            # Explicitly get the page content from the designated column
            content = raw_doc.metadata.get(CSV_CONTENT_COLUMN, '')

            # Create metadata dict from all *other* expected columns
            metadata = {}
            for col in EXPECTED_CSV_COLUMNS:
                if col != CSV_CONTENT_COLUMN:
                    metadata[col] = raw_doc.metadata.get(col, 'N/A') # Use N/A if column missing in a row

            # Add row number as metadata for potential debugging
            metadata['original_row'] = i

            # Check if content is valid
            if not content or not isinstance(content, str):
                 print(f"Warning: Row {i} has missing or invalid content in '{CSV_CONTENT_COLUMN}'. Skipping.")
                 continue

            # Create the cleaned document
            clean_doc = Document(page_content=content, metadata=metadata)
            original_documents_cleaned.append(clean_doc)
        # --- End manual creation --- 

        print(f"Processed {len(original_documents_cleaned)} valid documents.")
        if not original_documents_cleaned:
             return [], [] # Return empty lists if no valid docs processed

        # Split the cleaned documents
        chunked_documents = split_documents(original_documents_cleaned)
        return original_documents_cleaned, chunked_documents

    except FileNotFoundError:
        print(f"Error: CSV file not found at {CSV_FILE_PATH}")
        return [], []
    except KeyError as e:
        print(f"Error processing CSV row {i}: Missing expected column '{e}'. Check CSV header and EXPECTED_CSV_COLUMNS in data_loader.py.")
        return original_documents_cleaned, [] # Return what was processed so far
    except Exception as e:
        print(f"Error loading or processing CSV: {e}")
        return original_documents_cleaned, []

# Optional: Add text splitting logic here if posts are very long - REMOVED, now integrated above
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# def split_documents(documents, chunk_size=1000, chunk_overlap=200):
#     print(f"Splitting {len(documents)} documents into chunks...")
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
#     split_docs = text_splitter.split_documents(documents)
#     print(f"Split into {len(split_docs)} chunks.")
#     return split_docs 