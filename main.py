# main.py
import sys
import datetime # For report date
from config import PDF_OUTPUT_FILENAME, RETRIEVER_TOP_K
# Updated: data_loader now returns originals and chunks
from data_loader import load_and_chunk_documents
from vector_store_utils import get_embedding_function, create_or_load_vector_store, get_retriever
from llm_interface import get_llm, create_rag_chain
from pdf_generator import create_pdf
import traceback # For printing traceback on error

def run_analysis_pipeline(query: str):
    """Runs the full RAG pipeline for a given query."""
    print("\n--- Starting Analysis Pipeline ---")

    # 1. Initialize Embeddings
    try:
        embeddings = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}")
        return

    # 2. Load Originals and Chunk Documents
    original_docs, chunked_docs = load_and_chunk_documents()

    # Handle loading/chunking failures
    if not chunked_docs and not original_docs:
        print("Error: Failed to load any documents or chunks.")
        return
    elif not chunked_docs and original_docs:
        print("Warning: Documents loaded but chunking failed. Trying to proceed with existing vector store only.")
    elif not original_docs and chunked_docs:
        print("Error: Cannot proceed with full-document context without original documents.")
        return

    # Create lookup map: Store tuple (content, url) keyed by (title, date)
    original_doc_lookup = {}
    for doc in original_docs:
        title = doc.metadata.get('title', 'N/A')
        date_meta = doc.metadata.get('date', 'N/A')
        url = doc.metadata.get('url', '#') # Default URL if missing
        lookup_key = (title, date_meta)
        original_doc_lookup[lookup_key] = (doc.page_content, url)

    if not original_doc_lookup:
        print("Warning: Could not create lookup for original documents.")

    # 3. Create or Load Vector Store (using CHUNKS)
    vector_store = create_or_load_vector_store(chunked_docs, embeddings)
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

    # 6. Create RAG Chain
    try:
        rag_chain = create_rag_chain(retriever, llm)
    except Exception as e:
        print(f"Failed to create RAG chain: {e}")
        return

    # 7. Invoke Chain with User Query and Lookup
    print(f"\nInvoking RAG chain with query: '{query}'")
    analysis_result = None
    analyzed_docs_metadata = []
    try:
        invoke_input = {"question": query, "original_doc_lookup": original_doc_lookup}
        # Expect the chain to output a dict: {"analysis": ..., "analyzed_metadata": [...]}
        chain_output = rag_chain.invoke(invoke_input)

        # -- Check the output structure --
        if isinstance(chain_output, dict):
            analysis_result = chain_output.get('analysis', 'Error: Analysis not found in chain output.')
            analyzed_docs_metadata = chain_output.get('analyzed_metadata', [])
            print("\n--- Analysis Result --- (from dict)")
            print(analysis_result)
            print("-----------------------")
            print(f"--- Retrieved Metadata for {len(analyzed_docs_metadata)} Documents ---")
        else:
             # Fallback if chain output is unexpectedly just the analysis string
             print("Warning: Chain output was not a dictionary. Expected {'analysis': ..., 'analyzed_metadata': ...}.")
             analysis_result = str(chain_output) # Treat output as analysis string
             analyzed_docs_metadata = [] # Cannot extract metadata
             print("\n--- Analysis Result --- (fallback)")
             print(analysis_result)
             print("-----------------------\n")

    except Exception as e:
        print(f"Error during RAG chain invocation: {e}")
        traceback.print_exc()
        return

    if analysis_result is None:
        print("Error: Analysis generation failed or produced no result.")
        return

    # 8. Generate PDF
    generation_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    create_pdf(
        query=query,
        generation_date=generation_date,
        analysis_result=analysis_result,
        analyzed_docs=analyzed_docs_metadata, # Pass the list of dicts
        filename=PDF_OUTPUT_FILENAME
    )

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