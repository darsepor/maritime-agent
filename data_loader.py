# data_loader.py
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import MONGO_URI, MONGO_DATABASE_NAME, NEWS_COLLECTION_NAME, PATENTS_COLLECTION_NAME
from data_base import MongoHandler # Assuming MongoHandler is in data_base.py

# Define splitter configuration
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
        add_start_index=True,
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"Split into {len(split_docs)} chunks.")
    return split_docs

def _create_document_from_mongo_record(record, text_field_name='text'):
    """Helper to create a Langchain Document from a MongoDB record."""
    content = record.get(text_field_name, '')
    if not content or not isinstance(content, str):
        print(f"Warning: Record with _id {record.get('_id')} has missing or invalid content in '{text_field_name}'. Skipping.")
        return None

    metadata = {key: value for key, value in record.items() if key not in [text_field_name, '_id']}
    metadata['mongo_id'] = str(record['_id']) # Ensure mongo_id is stored and is a string

    # Convert any non-serializable metadata to string (e.g., datetime objects)
    for k, v in metadata.items():
        if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
            metadata[k] = str(v)
            
    return Document(page_content=content, metadata=metadata)

def load_news_from_mongo(mongo_handler, limit=0, skip=0, since_timestamp=None):
    """Loads news documents from MongoDB, optionally filtered by since_timestamp."""
    print(f"Loading news from MongoDB (collection: {NEWS_COLLECTION_NAME}, limit: {limit}, skip: {skip})...")
    news_records = mongo_handler.get_news_for_vectorization(limit=limit, skip=skip, since_timestamp=since_timestamp)
    documents = []
    for record in news_records:
        doc = _create_document_from_mongo_record(record, text_field_name='text')
        if doc:
            doc.metadata['doc_type'] = 'news'
            documents.append(doc)
    print(f"Loaded {len(documents)} news documents from MongoDB.")
    return documents

def load_patents_from_mongo(mongo_handler, limit=0, skip=0, since_timestamp=None):
    """Loads patent documents from MongoDB, optionally filtered by since_timestamp."""
    print(f"Loading patents from MongoDB (collection: {PATENTS_COLLECTION_NAME}, limit: {limit}, skip: {skip})...")
    patent_records = mongo_handler.get_patents_for_vectorization(limit=limit, skip=skip, since_timestamp=since_timestamp)
    documents = []
    for record in patent_records:
        doc = _create_document_from_mongo_record(record, text_field_name='text')
        if doc:
            doc.metadata['doc_type'] = 'patent'
            documents.append(doc)
    print(f"Loaded {len(documents)} patent documents from MongoDB.")
    return documents

def load_and_chunk_documents(data_types="all", limit_per_type=0, skip_offsets=None, last_build_timestamp=None):
    """
    Loads documents from MongoDB, creates Document objects, splits, returns originals and chunks.
    Args:
        data_types (str or list): "news", "patents", "all", or a list like ["news", "patents"].
        limit_per_type (int): Max number of documents to load per type for this batch. 0 for no limit in this call.
        skip_offsets (dict, optional): A dictionary like {'news': 0, 'patents': 0} for skipping documents.
        last_build_timestamp (datetime or str, optional): If provided, load docs newer than this.
    """
    mongo_handler = MongoHandler(MONGO_URI, MONGO_DATABASE_NAME)
    original_documents_cleaned = []
    skip_offsets = skip_offsets or {}
    
    if isinstance(data_types, str):
        if data_types.lower() == "all":
            data_types_to_load = ["news", "patents"]
        else:
            data_types_to_load = [data_types.lower()]
    elif isinstance(data_types, list):
        data_types_to_load = [dt.lower() for dt in data_types]
    else:
        print("Error: Invalid data_types argument. Must be 'news', 'patents', 'all', or a list.")
        return [], []

    if "news" in data_types_to_load:
        current_skip_news = skip_offsets.get("news", 0)
        original_documents_cleaned.extend(load_news_from_mongo(mongo_handler, limit=limit_per_type, skip=current_skip_news, since_timestamp=last_build_timestamp))
    
    if "patents" in data_types_to_load:
        current_skip_patents = skip_offsets.get("patents", 0)
        original_documents_cleaned.extend(load_patents_from_mongo(mongo_handler, limit=limit_per_type, skip=current_skip_patents, since_timestamp=last_build_timestamp))

    if not original_documents_cleaned:
        print("Warning: No new or matching documents loaded from MongoDB.")
        return [], []

    print(f"Processed {len(original_documents_cleaned)} new/updated documents from MongoDB for vectorization.")
    chunked_documents = split_documents(original_documents_cleaned)
    return original_documents_cleaned, chunked_documents

# Example usage (optional, for testing)
if __name__ == '__main__':
    # To test, ensure your MongoDB is running and populated, and config.py is set up.
    # You also need data_base.py with MongoHandler in the same directory or accessible.
    
    print("Testing data loader with MongoDB...")
    
    # Test loading news
    # print("\\n--- Loading News ---")
    # original_news, chunked_news = load_and_chunk_documents(data_types="news", limit_per_type=5)
    # if original_news:
    #     print(f"First original news doc: {original_news[0].page_content[:100]}...")
    #     print(f"Metadata of first news doc: {original_news[0].metadata}")
    # if chunked_news:
    #     print(f"First chunked news doc: {chunked_news[0].page_content[:100]}...")
    #     print(f"Metadata of first chunked news doc: {chunked_news[0].metadata}")

    # Test loading patents
    # print("\\n--- Loading Patents ---")
    # original_patents, chunked_patents = load_and_chunk_documents(data_types="patents", limit_per_type=5)
    # if original_patents:
    #     print(f"First original patent doc: {original_patents[0].page_content[:200]}...") # Patents can be long
    #     print(f"Metadata of first patent doc: {original_patents[0].metadata}")
    # if chunked_patents:
    #     print(f"First chunked patent doc: {chunked_patents[0].page_content[:100]}...")
    #     print(f"Metadata of first chunked patent doc: {chunked_patents[0].metadata}")

    # Test loading all
    print("\\n--- Loading All ---")
    original_all, chunked_all = load_and_chunk_documents(data_types="all", limit_per_type=2) # Small limit for combined test
    if original_all:
        print(f"Total original docs loaded: {len(original_all)}")
        # for doc in original_all:
        #     print(f"Type: {doc.metadata.get('url', 'N/A')[:30]}, Mongo ID: {doc.metadata.get('mongo_id')}") # Quick check of type/id
    if chunked_all:
        print(f"Total chunked docs: {len(chunked_all)}")
        # for chunk in chunked_all:
            # print(f"Chunk from Mongo ID: {chunk.metadata.get('mongo_id')}, Start Index: {chunk.metadata.get('start_index')}")

    print("\\nData loading test complete.") 