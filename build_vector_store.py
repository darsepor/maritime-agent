# build_vector_store.py
import chromadb
import hashlib
import time

# Use the existing functions/config for loading, chunking, embeddings
from data_loader import load_and_chunk_documents
from vector_store_utils import get_embedding_function
from config import VECTOR_STORE_PATH, LOOKUP_FILE_PATH
from pickle_utils import save_pickle

def generate_deterministic_id(text_content):
    """Generates a SHA-256 hash for the text content."""
    return hashlib.sha256(text_content.encode('utf-8')).hexdigest()

def main():
    print("--- Starting Vector Store Build/Update Process ---")
    start_time = time.time()

    # 1. Load and Chunk Documents
    original_docs, chunked_docs = load_and_chunk_documents()
    if not chunked_docs:
        print("Error: No document chunks were generated. Aborting build.")
        return

    # 2. Create Original Document Lookup (same as in main.py before)
    print("Creating original document lookup dictionary...")
    original_doc_lookup = {}
    for doc in original_docs:
        title = doc.metadata.get('title', 'N/A')
        date_meta = doc.metadata.get('date', 'N/A')
        url = doc.metadata.get('url', '#')
        lookup_key = (title, date_meta)
        original_doc_lookup[lookup_key] = (doc.page_content, url)

    if not original_doc_lookup:
        print("Warning: Original document lookup is empty.")

    # 3. Initialize Embedding Function
    try:
        embeddings_model = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}. Aborting build.")
        return

    # 4. Prepare Data for ChromaDB (with deterministic IDs)
    print("Preparing data for vector store...")
    ids = []
    documents_content = []
    metadatas = []
    embeddings_list = []

    print("Generating embeddings and deterministic IDs...")
    # Generate embeddings for all chunks at once for efficiency
    try:
        all_chunk_texts = [chunk.page_content for chunk in chunked_docs]
        all_embeddings = embeddings_model.embed_documents(all_chunk_texts)
        if len(all_embeddings) != len(chunked_docs):
             raise ValueError("Mismatch between number of chunks and generated embeddings.")
    except Exception as e:
         print(f"Error generating embeddings: {e}. Aborting build.")
         return

    for i, chunk in enumerate(chunked_docs):
        deterministic_id = generate_deterministic_id(chunk.page_content)
        ids.append(deterministic_id)
        documents_content.append(chunk.page_content)
        metadatas.append(chunk.metadata)
        embeddings_list.append(all_embeddings[i]) # Use pre-generated embedding

    # --- Filter out duplicate IDs before upserting ---
    print(f"Generated {len(ids)} total IDs. Filtering duplicates...")
    unique_data = {}
    filtered_ids = []
    filtered_embeddings = []
    filtered_metadatas = []
    filtered_documents = []

    for i, doc_id in enumerate(ids):
        if doc_id not in unique_data:
            unique_data[doc_id] = True # Mark ID as seen
            filtered_ids.append(doc_id)
            filtered_embeddings.append(embeddings_list[i])
            filtered_metadatas.append(metadatas[i])
            filtered_documents.append(documents_content[i])

    print(f"Filtered down to {len(filtered_ids)} unique IDs for upsert.")
    # --- End filtering ---

    # 5. Connect to ChromaDB and Upsert Data
    print(f"Connecting to persistent vector store at: {VECTOR_STORE_PATH}")
    try:
        chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
        # Collection name should ideally match what LangChain uses if mixing,
        # but let's use a distinct one or ensure consistency.
        # Default LangChain Chroma collection name is often 'langchain'
        # Let's use 'blog_posts' for clarity
        collection_name = "blog_posts_collection"
        collection = chroma_client.get_or_create_collection(name=collection_name)

        print(f"Upserting {len(filtered_ids)} documents into collection '{collection_name}'...") # Use filtered count
        # Use upsert to add or update based on deterministic IDs
        collection.upsert(
            ids=filtered_ids, # Use filtered list
            embeddings=filtered_embeddings, # Use filtered list
            metadatas=filtered_metadatas, # Use filtered list
            documents=filtered_documents # Use filtered list
        )
        print("Upsert operation completed.")
        print(f"Vector store now contains {collection.count()} documents.")

    except Exception as e:
        print(f"Error interacting with ChromaDB: {e}. Aborting build.")
        return

    # 6. Save the Lookup Dictionary
    print(f"Saving original document lookup dictionary to: {LOOKUP_FILE_PATH}")
    save_pickle(original_doc_lookup, LOOKUP_FILE_PATH)

    end_time = time.time()
    print(f"--- Vector Store Build/Update Finished in {end_time - start_time:.2f} seconds ---")

if __name__ == "__main__":
    main() 