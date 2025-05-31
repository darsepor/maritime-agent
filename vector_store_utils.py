# vector_store_utils.py
import os
import torch # Import torch to check for CUDA
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores import FAISS
# from langchain_community.embeddings import HuggingFaceEmbeddings # Old import
from langchain_huggingface import HuggingFaceEmbeddings # New import
from config import EMBEDDING_MODEL_NAME, VECTOR_STORE_PATH
# Removed ChromaDB-specific embedding function import

def get_embedding_function():
    """Initializes and returns the embedding function."""
    print(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")

    # Determine device based on CUDA availability
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device} for embeddings")

    # Initialize the base HuggingFaceEmbeddings
    hf_embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True}
    )
    
    # Wrap the HuggingFaceEmbeddings with ChromaDB's utility
    # No need for ChromaDB-specific wrapping; FAISS can use hf_embeddings directly or with custom handling
    
    # Return the appropriate embedding function based on caller context. For now, we return
    # a ChromaDB compatible EF if it's doing direct ChromaDB operations,
    # but since we're focusing on build_vector_store.py, we prioritize that format.
    # For now, return the HuggingFace embeddings compatible with FAISS
    return hf_embeddings

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