# build_vector_store.py
import chromadb
import hashlib
import time
import os # For reading/writing timestamp file
import datetime # For generating current timestamp
from dateutil import parser as date_parser # For parsing stored timestamp
import pickle
import numpy as np

# Use the existing functions/config for loading, chunking, embeddings
from data_loader import load_and_chunk_documents
from vector_store_utils import get_embedding_function
from config import VECTOR_STORE_PATH, LAST_BUILD_TIMESTAMP_PATH, MONGO_URI, MONGO_DATABASE_NAME
from data_base import MongoHandler # For counting documents
from langchain_community.vectorstores import FAISS

# from pickle_utils import save_pickle # Removed pickle_utils import

def generate_deterministic_id(text_content):
    """Generates a SHA-256 hash for the text content."""
    return hashlib.sha256(text_content.encode('utf-8')).hexdigest()

def read_last_build_timestamp(path):
    """Reads the last build timestamp from the specified file."""
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                timestamp_str = f.read().strip()
                if timestamp_str:
                    # Attempt to parse a full ISO format timestamp first
                    try:
                        return date_parser.isoparse(timestamp_str)
                    except ValueError:
                        # Fallback for simpler date formats if needed, though ISO is preferred
                        print(f"Warning: Could not parse '{timestamp_str}' as full ISO datetime. Attempting simpler parse.")
                        return date_parser.parse(timestamp_str) # More general parser
        except Exception as e:
            print(f"Error reading or parsing timestamp from {path}: {e}. Proceeding with full build.")
    return None

def write_current_build_timestamp(path):
    """Writes the current UTC timestamp to the specified file in ISO format."""
    try:
        # Store timestamp in UTC and ISO format for consistency
        current_utc_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(path, 'w') as f:
            f.write(current_utc_timestamp)
        print(f"Successfully wrote current build timestamp ({current_utc_timestamp}) to {path}")
    except Exception as e:
        print(f"Error writing timestamp to {path}: {e}")

def main(data_types_to_process="all", overall_doc_limit_per_type=0):
    print("--- Starting Vector Store Build/Update Process ---")
    start_time = time.time()

    # 0. Read the last build timestamp
    last_build_ts = read_last_build_timestamp(LAST_BUILD_TIMESTAMP_PATH)
    if last_build_ts:
        print(f"Last build timestamp found: {last_build_ts}. Loading documents since this time.")
    else:
        print("No last build timestamp found. Performing a full load of all documents.")

    # 1. Initialize Embedding Function
    try:
        embeddings_model = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}. Aborting build.")
        return

    # 2. Connect to FAISS (in-memory, save to disk later)
    print(f"Creating FAISS vector store (in-memory, will save to disk at: {VECTOR_STORE_PATH})")
    try:
        # Initialize an empty FAISS index with the embedding model
        # We'll save it to disk at the end if successful
        faiss_store = None
        index_path = f"{VECTOR_STORE_PATH}/faiss_index"
        if os.path.exists(index_path):
            print(f"Loading existing FAISS index from {index_path}...")
            try:
                faiss_store = FAISS.load_local(index_path, embeddings_model, allow_dangerous_deserialization=True)
                print(f"Loaded existing FAISS store with {len(faiss_store.index_to_docstore_id)} documents.")
            except Exception as e:
                print(f"Error loading existing FAISS index: {e}. Starting fresh.")
                faiss_store = None
        if faiss_store is None:
            print("No existing FAISS index found or failed to load. Creating a new one.")
            # Create a new empty FAISS store without relying on embed_documents
            from langchain_community.vectorstores.faiss import FAISS as FAISSStore
            from langchain_community.vectorstores.utils import DistanceStrategy
            import faiss
            # Define the dimension of embeddings (based on all-MiniLM-L6-v2, it's 384)
            dimension = 384
            # Create a FAISS index manually
            index = faiss.IndexFlatL2(dimension)
            # Wrap it in a docstore for LangChain compatibility
            from langchain_community.docstore.in_memory import InMemoryDocstore
            from langchain_community.vectorstores.faiss import dependable_faiss_import
            dependable_faiss_import()  # Ensure FAISS is imported
            docstore = InMemoryDocstore({})
            index_to_docstore_id = {}
            # Manually create the FAISS store without an embedding function
            faiss_store = FAISSStore(
                embedding_function=embeddings_model,  # We'll handle embeddings manually if needed
                index=index,
                docstore=docstore,
                index_to_docstore_id=index_to_docstore_id,
                distance_strategy=DistanceStrategy.EUCLIDEAN_DISTANCE
            )
            print("Initialized empty FAISS store manually.")
    except Exception as e:
        print(f"Error initializing FAISS store: {e}. Aborting build.")
        return

    mongo_handler = MongoHandler(MONGO_URI, MONGO_DATABASE_NAME)
    
    RAW_DOC_BATCH_SIZE = 500  # Number of raw documents to process from MongoDB at a time (increased from 100)
    processed_doc_counts = {"news": 0, "patents": 0}
    total_chunks_processed_overall = 0

    if isinstance(data_types_to_process, str):
        if data_types_to_process.lower() == "all":
            doc_types_to_iterate = ["news", "patents"]
        else:
            doc_types_to_iterate = [data_types_to_process.lower()]
    elif isinstance(data_types_to_process, list):
        # Check if 'all' is in the list, case-insensitive
        if any(dt.lower() == "all" for dt in data_types_to_process):
            doc_types_to_iterate = ["news", "patents"]
        else:
            doc_types_to_iterate = [dt.lower() for dt in data_types_to_process]
    else:
        print("Error: Invalid data_types_to_process. Must be 'news', 'patents', 'all', or a list.")
        return

    for doc_type in doc_types_to_iterate:
        print(f"--- Processing document type: {doc_type.upper()} ---")
        current_skip = 0
        
        if doc_type == "news":
            total_docs_for_type = mongo_handler.count_news_for_vectorization(since_timestamp=last_build_ts)
        elif doc_type == "patents":
            total_docs_for_type = mongo_handler.count_patents_for_vectorization(since_timestamp=last_build_ts)
        else:
            print(f"Unknown document type: {doc_type}. Skipping.")
            continue
            
        print(f"Found {total_docs_for_type} {doc_type} documents to process based on timestamp.")
        
        # Apply overall_doc_limit_per_type if specified
        docs_to_fetch_for_type = total_docs_for_type
        if overall_doc_limit_per_type > 0 and overall_doc_limit_per_type < total_docs_for_type:
            docs_to_fetch_for_type = overall_doc_limit_per_type
            print(f"Applying overall limit: will process up to {docs_to_fetch_for_type} {doc_type} documents.")

        while current_skip < docs_to_fetch_for_type:
            limit_for_this_batch = RAW_DOC_BATCH_SIZE
            # Adjust limit if overall_doc_limit_per_type would be exceeded
            if overall_doc_limit_per_type > 0 and (current_skip + RAW_DOC_BATCH_SIZE > docs_to_fetch_for_type):
                 limit_for_this_batch = docs_to_fetch_for_type - current_skip

            if limit_for_this_batch <= 0: # Should not happen if loop condition is correct, but as safeguard
                break

            print(f"Fetching raw {doc_type} batch: limit={limit_for_this_batch}, skip={current_skip}")
            
            _, chunked_docs = load_and_chunk_documents(
                data_types=[doc_type], # Process one type at a time
                limit_per_type=limit_for_this_batch,
                skip_offsets={doc_type: current_skip},
                last_build_timestamp=last_build_ts
            )

            if not chunked_docs:
                print(f"No more {doc_type} documents found or processed in this batch (skip: {current_skip}). Moving to next type or finishing.")
                break # Exit while loop for this doc_type

            print(f"Loaded and chunked {len(chunked_docs)} chunks from {doc_type} batch.")
            
            # --- Start: Processing for this batch of chunks ---
            ids = []
            documents_content = []
            metadatas_list = []
            embeddings_list = []

            print("Generating embeddings for current batch...")
            try:
                all_chunk_texts = [chunk.page_content for chunk in chunked_docs]
                if not all_chunk_texts:
                    print("No text content in current chunk batch. Skipping.")
                    current_skip += limit_for_this_batch
                    processed_doc_counts[doc_type] += limit_for_this_batch
                    continue

                all_embeddings = embeddings_model.embed_documents(all_chunk_texts)
                if len(all_embeddings) != len(chunked_docs):
                    raise ValueError("Mismatch between number of chunks and generated embeddings in batch.")
            except Exception as e:
                print(f"Error generating embeddings for batch: {e}. Skipping this batch.")
                current_skip += limit_for_this_batch
                processed_doc_counts[doc_type] += limit_for_this_batch
                continue

            for i_chunk, chunk in enumerate(chunked_docs):
                if not chunk.page_content:
                    print(f"Warning: Chunk has empty content. Skipping. Metadata: {chunk.metadata}")
                    continue

                deterministic_id = generate_deterministic_id(chunk.page_content + str(chunk.metadata.get('mongo_id')))
                ids.append(deterministic_id)
                documents_content.append(chunk.page_content)

                sanitized_meta = {}
                for key, value in chunk.metadata.items():
                    if isinstance(value, list):
                        sanitized_meta[key] = str(value)
                    elif value is None:
                        sanitized_meta[key] = ""
                    else:
                        sanitized_meta[key] = value
                metadatas_list.append(sanitized_meta)
                embeddings_list.append(all_embeddings[i_chunk])

            if not ids:
                print("No valid data to upsert from this batch. Continuing.")
                current_skip += limit_for_this_batch
                processed_doc_counts[doc_type] += limit_for_this_batch
                continue

            # Filter duplicates (within this batch)
            unique_data_store = {}
            filtered_ids = []
            filtered_embeddings = []
            filtered_metadatas_batch = []
            filtered_documents_batch = []

            for i_unique, doc_id in enumerate(ids):
                if doc_id not in unique_data_store:
                    unique_data_store[doc_id] = True
                    filtered_ids.append(doc_id)
                    filtered_embeddings.append(embeddings_list[i_unique])
                    filtered_metadatas_batch.append(metadatas_list[i_unique])
                    filtered_documents_batch.append(documents_content[i_unique])

            print(f"Filtered down to {len(filtered_ids)} unique items in this batch for upsert.")

            if filtered_ids:
                print(f"Adding {len(filtered_ids)} items to FAISS store...")
                try:
                    embeddings_for_faiss = [emb.tolist() if isinstance(emb, np.ndarray) else emb for emb in filtered_embeddings]
                    faiss_store.add_embeddings(
                        text_embeddings=list(zip(filtered_documents_batch, embeddings_for_faiss)),
                        metadatas=filtered_metadatas_batch,
                        ids=filtered_ids
                    )
                    print("FAISS batch added successfully.")
                    total_chunks_processed_overall += len(filtered_ids)
                except Exception as e:
                    print(f"Error adding batch to FAISS store: {e}. Skipping this batch.")

            # --- End: Processing for this batch of chunks ---
            current_skip += limit_for_this_batch
            processed_doc_counts[doc_type] += limit_for_this_batch
            print(f"Completed processing raw document batch for {doc_type}. Processed so far for this type: {current_skip}/{docs_to_fetch_for_type}")

        print(f"--- Finished processing document type: {doc_type.upper()}. Total processed for this type: {processed_doc_counts[doc_type]} raw documents ---")

    # End of iterating through doc_types

    print(f"--- All document types processed. Total chunks added to FAISS store: {total_chunks_processed_overall} ---")
    print(f"Final document counts from MongoDB processing attempts: {processed_doc_counts}")
    
    # Write timestamp only if the entire process (or a significant portion) seems successful.
    # This condition might need refinement.
    if total_chunks_processed_overall > 0 or (
        last_build_ts is None and sum(processed_doc_counts.values()) == 0
    ):
        write_current_build_timestamp(LAST_BUILD_TIMESTAMP_PATH)
        try:
            print(f"Saving FAISS index to {index_path}...")
            faiss_store.save_local(index_path)
            print("FAISS index saved successfully.")
        except Exception as e:
            print(f"Error saving FAISS index: {e}. Index not saved, but process completed.")
    else:
        print("No new chunks were processed and added. Timestamp not updated.")

    end_time = time.time()
    print(f"--- Vector Store Build/Update Finished in {end_time - start_time:.2f} seconds ---")

if __name__ == "__main__":
    # Example: Process all documents, in batches of RAW_DOC_BATCH_SIZE (e.g., 500)
    # main(data_types_to_process="all", overall_doc_limit_per_type=0)
    
    # Example: For testing, process only 1000 news documents and 500 patent documents in total
    # main(data_types_to_process="all", overall_doc_limit_per_type=0) # Small limit for testing the new batching
    main(data_types_to_process=["all"], overall_doc_limit_per_type=0) # Drastically reduce to 1 news doc for testing
    
    # Example: Process only news, all available documents
    # main(data_types_to_process="news", overall_doc_limit_per_type=0)
    
    # Example: To build/update only patents, limit to 5 documents:
    # main(data_types_to_process="patents", overall_doc_limit_per_type=5)
    
    # Example: To build/update all (news and patents), no limit (loads all):
    # main(data_types_to_process="all", overall_doc_limit_per_type=0)
    
    # Example: To build/update a specific list of types:
    # main(data_types_to_process=["news", "patents"], overall_doc_limit_per_type=2) 