# data_loader.py
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import CSV_FILE_PATH, CSV_CONTENT_COLUMN, CSV_METADATA_COLUMNS

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
    """Loads documents from CSV, splits them, and returns both originals and chunks."""
    print(f"Loading documents from: {CSV_FILE_PATH}")
    loader = CSVLoader(
        file_path=CSV_FILE_PATH,
        source_column=CSV_CONTENT_COLUMN, # Which column becomes Document.page_content
        metadata_columns=CSV_METADATA_COLUMNS, # Other columns become metadata
        encoding='utf-8', # Specify encoding if needed
        csv_args={
            'delimiter': ',',
            'quotechar': '"',
            # Add other pandas read_csv args if necessary
        }
    )
    original_documents = []
    chunked_documents = []
    try:
        original_documents = loader.load()
        print(f"Loaded {len(original_documents)} original documents.")
        if not original_documents:
            print("Warning: No documents loaded from CSV. Check CSV format and content.")
            return original_documents, chunked_documents # Return empty lists

        # Split the loaded documents
        chunked_documents = split_documents(original_documents)
        return original_documents, chunked_documents

    except FileNotFoundError:
        print(f"Error: CSV file not found at {CSV_FILE_PATH}")
        return [], [] # Return empty lists
    except Exception as e:
        print(f"Error loading or splitting CSV: {e}")
        # Potentially check specific columns existence errors
        return original_documents, []

# Optional: Add text splitting logic here if posts are very long - REMOVED, now integrated above
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# def split_documents(documents, chunk_size=1000, chunk_overlap=200):
#     print(f"Splitting {len(documents)} documents into chunks...")
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
#     split_docs = text_splitter.split_documents(documents)
#     print(f"Split into {len(split_docs)} chunks.")
#     return split_docs 