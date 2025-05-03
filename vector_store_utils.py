# vector_store_utils.py
import os
import torch # Import torch to check for CUDA
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import EMBEDDING_MODEL_NAME, VECTOR_STORE_PATH

def get_embedding_function():
    """Initializes and returns the embedding function."""
    print(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")

    # Determine device based on CUDA availability
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device} for embeddings")

    # Use Langchain's wrapper for sentence-transformers
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': device} # Dynamically set device
        )
    print("Embedding model initialized.")
    return embeddings

def get_retriever(vector_store, top_k):
    """Creates a retriever from the vector store."""
    if not vector_store:
        print("Error: Cannot create retriever without a valid vector store.")
        return None
    try:
        retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
        print(f"Retriever configured to fetch top {top_k} results.")
        return retriever
    except Exception as e:
         print(f"Error creating retriever: {e}")
         return None 