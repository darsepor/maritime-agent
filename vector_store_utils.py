# vector_store_utils.py
import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import EMBEDDING_MODEL_NAME, VECTOR_STORE_PATH

def get_embedding_function():
    """Initializes and returns the embedding function."""
    print(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
    # Use Langchain's wrapper for sentence-transformers
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'} # Or 'cuda' if available/configured
        )
    print("Embedding model initialized.")
    return embeddings

def create_or_load_vector_store(documents, embeddings):
    """
    Creates a new Chroma vector store or loads an existing one from disk.
    If store exists, it loads it and potentially adds new/updated documents.
    If store doesn't exist, it creates it using the provided documents.
    """
    vector_store = None
    if os.path.exists(VECTOR_STORE_PATH) and os.listdir(VECTOR_STORE_PATH):
        print(f"Loading existing vector store from: {VECTOR_STORE_PATH}")
        try:
            vector_store = Chroma(
                persist_directory=VECTOR_STORE_PATH,
                embedding_function=embeddings
            )
            print(f"Existing vector store loaded. Count: {vector_store._collection.count()}")
            # Decide if you want to *add* the currently loaded documents.
            # This handles cases where the source CSV changed or splitting strategy changed.
            # If the number of documents provided is > 0, we add them.
            # Note: This doesn't handle *deleting* old documents automatically.
            # For a true sync, deleting the store dir before running might be needed.
            if documents:
                 print(f"Adding {len(documents)} documents/chunks to the existing store...")
                 # Consider getting existing IDs to avoid duplicates if necessary,
                 # but for simplicity, Chroma handles ID conflicts by default (upsert).
                 vector_store.add_documents(documents)
                 print("Documents added/updated in the store.")
                 # Optional: Persist changes explicitly if needed, though Chroma often handles this.
                 # vector_store.persist()

        except Exception as e:
            print(f"Error loading or updating existing vector store: {e}")
            # Fallback: Try creating anew if loading failed badly and documents exist
            if documents:
                 print("Attempting to create vector store from scratch...")
                 vector_store = None # Reset to trigger creation below
            else:
                 return None # Cannot proceed

    # If store wasn't loaded or loading failed and we fell back
    if not vector_store:
        if documents:
            print(f"Creating new vector store at: {VECTOR_STORE_PATH}")
            try:
                vector_store = Chroma.from_documents(
                    documents=documents,
                    embedding=embeddings,
                    persist_directory=VECTOR_STORE_PATH # This saves the embeddings
                )
                print("Vector store created and populated.")
            except Exception as e:
                print(f"Error creating new vector store: {e}")
                return None
        else:
            print("Error: Vector store path does not exist and no documents were provided to create a new one.")
            return None

    return vector_store

def get_retriever(vector_store, top_k):
    """Creates a retriever from the vector store."""
    if not vector_store:
        return None
    retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
    print(f"Retriever configured to fetch top {top_k} results.")
    return retriever 