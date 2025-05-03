# main.py
import sys
import os # For checking file existence
import datetime
import traceback

# Use LangChain interface for loading persistent store
from langchain_community.vectorstores import Chroma

from config import PDF_OUTPUT_FILENAME, RETRIEVER_TOP_K, VECTOR_STORE_PATH, LOOKUP_FILE_PATH
# Removed data_loader import as it's no longer used here
from vector_store_utils import get_embedding_function, get_retriever # Removed create_or_load
from llm_interface import get_llm, create_rag_chain
from pdf_generator import create_pdf
from pickle_utils import load_pickle # Utility for loading the lookup dict

def run_analysis_pipeline(query: str):
    """Runs the RAG pipeline using a pre-built vector store and lookup file."""
    print("\n--- Starting Analysis Pipeline (using pre-built store) ---")

    # --- Check if required pre-built files exist --- 
    if not os.path.exists(VECTOR_STORE_PATH) or not os.listdir(VECTOR_STORE_PATH):
        print(f"Error: Vector store not found or empty at {VECTOR_STORE_PATH}.")
        print("Please run 'python build_vector_store.py' first.")
        return
    if not os.path.exists(LOOKUP_FILE_PATH):
        print(f"Error: Original document lookup file not found at {LOOKUP_FILE_PATH}.")
        print("Please run 'python build_vector_store.py' first.")
        return
    # --- End Check --- 

    # 1. Initialize Embeddings (needed to load Chroma store)
    try:
        embeddings = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}")
        return

    # 2. Load the pre-built Vector Store
    print(f"Loading pre-built vector store from: {VECTOR_STORE_PATH}")
    try:
        # We need to specify the collection name used during the build
        collection_name = "blog_posts_collection"
        vector_store = Chroma(
            persist_directory=VECTOR_STORE_PATH,
            embedding_function=embeddings,
            collection_name=collection_name
        )
        print(f"Vector store loaded. Contains {vector_store._collection.count()} documents.")
    except Exception as e:
        print(f"Error loading vector store: {e}")
        print("Ensure the store was built correctly and the collection name matches.")
        return

    # 3. Load the pre-built Original Document Lookup Dictionary
    print(f"Loading original document lookup from: {LOOKUP_FILE_PATH}")
    original_doc_lookup = load_pickle(LOOKUP_FILE_PATH)
    if original_doc_lookup is None:
        print("Failed to load original document lookup. Aborting.")
        return
    if not isinstance(original_doc_lookup, dict) or not original_doc_lookup:
         print("Warning: Loaded original document lookup is empty or not a dictionary.")
         # Depending on requirements, maybe allow continuing or abort.

    # 4. Get Retriever
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

    # 7. Invoke Chain with User Query and Loaded Lookup
    print(f"\nInvoking RAG chain with query: '{query}'")
    analysis_result = None
    analyzed_docs_metadata = []
    try:
        invoke_input = {"question": query, "original_doc_lookup": original_doc_lookup}
        chain_output = rag_chain.invoke(invoke_input)

        if isinstance(chain_output, dict):
            analysis_result = chain_output.get('analysis', 'Error: Analysis not found')
            analyzed_docs_metadata = chain_output.get('analyzed_metadata', [])
            print("\n--- Analysis Result --- (from dict)")
            print(analysis_result)
            print("-----------------------")
            print(f"--- Retrieved Metadata for {len(analyzed_docs_metadata)} Documents ---")
        else:
             print("Warning: Chain output was not a dictionary.")
             analysis_result = str(chain_output)
             analyzed_docs_metadata = []
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
        analyzed_docs=analyzed_docs_metadata,
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