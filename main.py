# main.py
import sys
from config import PDF_OUTPUT_FILENAME, RETRIEVER_TOP_K
# Updated: data_loader now returns originals and chunks
from data_loader import load_and_chunk_documents
from vector_store_utils import get_embedding_function, create_or_load_vector_store, get_retriever
from llm_interface import get_llm, create_rag_chain
from pdf_generator import create_pdf

def run_analysis_pipeline(query: str):
    """Runs the full RAG pipeline for a given query."""
    print("\n--- Starting Analysis Pipeline ---")

    # 1. Initialize Embeddings (do this early)
    try:
        embeddings = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}")
        return

    # 2. Load Originals and Chunk Documents
    original_docs, chunked_docs = load_and_chunk_documents()

    if not chunked_docs and not original_docs:
        # If loading failed completely
        print("Error: Failed to load any documents or chunks.")
        return
    elif not chunked_docs and original_docs:
        # Might happen if splitting failed after loading
        print("Warning: Documents loaded but chunking failed. Trying to proceed with existing vector store if possible.")
        # Allow proceeding, vector store logic will handle chunked_docs being empty
    elif not original_docs and chunked_docs:
         # This case should theoretically not happen with current logic
         print("Warning: Chunks created but original documents list is empty? Check data_loader.py")
         # We need originals for the lookup later, so cannot proceed with full-doc context
         # Fallback: Could potentially run original RAG with just chunks here if desired.
         print("Error: Cannot proceed with full-document context without original documents.")
         return

    # Create a lookup map for original documents based on metadata (e.g., title+date)
    # Assuming title + date is unique enough. If not, add a unique ID in data_loader.
    original_doc_lookup = {
        (doc.metadata.get('title', 'N/A'), doc.metadata.get('date', 'N/A')): doc.page_content
        for doc in original_docs
    }
    if not original_doc_lookup:
         print("Warning: Could not create lookup for original documents.")
         # Allow proceeding if only using existing vector store maybe?

    # 3. Create or Load Vector Store (using CHUNKS)
    vector_store = create_or_load_vector_store(
         chunked_docs, # Use chunks for vector store
         embeddings
         )
    if not vector_store:
        print("Failed to create or load the vector store. Cannot proceed.")
        return

    # 4. Get Retriever (operates on CHUNKS)
    retriever = get_retriever(vector_store, RETRIEVER_TOP_K)
    if not retriever:
        print("Failed to create retriever. Cannot proceed.")
        return

    # 5. Initialize LLM
    try:
        llm = get_llm()
    except Exception as e:
        print(f"Failed to initialize LLM: {e}")
        return

    # 6. Create RAG Chain - THIS WILL NEED MODIFICATION IN llm_interface.py
    # We now need to pass the original_doc_lookup to the chain creation/execution
    try:
        rag_chain = create_rag_chain(retriever, llm, original_doc_lookup)
    except Exception as e:
        print(f"Failed to create RAG chain: {e}")
        return

    # 7. Invoke Chain with User Query
    print(f"\nInvoking RAG chain with query: '{query}'")
    try:
        # The chain internally handles retrieving chunks and fetching full docs
        analysis_result = rag_chain.invoke(query)
        print("\n--- Analysis Result ---")
        print(analysis_result)
        print("-----------------------\n")
    except Exception as e:
        print(f"Error during RAG chain invocation: {e}")
        return

    # 8. Generate PDF
    create_pdf(analysis_result, PDF_OUTPUT_FILENAME)

    print("\n--- Analysis Pipeline Finished ---")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = "Summarize the main challenges discussed regarding AI implementation in healthcare."
        print(f"No query provided, using default: '{user_query}'")

    from config import GEMINI_API_KEY
    if GEMINI_API_KEY:
         run_analysis_pipeline(user_query)
    else:
         print("Pipeline cannot run because GEMINI_API_KEY is not set.") 