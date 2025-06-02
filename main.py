# main.py
import sys
import os # For checking file existence
import datetime
import traceback
import warnings  # To silence noisy deprecation warnings
import logging


# Use LangChain interface for loading persistent store
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate

from config import PDF_OUTPUT_FILENAME, RETRIEVER_TOP_K, VECTOR_STORE_PATH # Removed unused Mongo config imports for main
from vector_store_utils import get_embedding_function # get_retriever might not be directly used here anymore
from llm_interface import get_llm, create_rag_chain # get_llm now takes temperature
from pdf_generator import create_pdf

# Silence the very noisy Convert_system_message_to_human deprecation warning that
# LangChain/Google-GenAI currently emits every invocation.  We only need to see
# it once.
warnings.filterwarnings(
    "ignore",
    message="Convert_system_message_to_human will be deprecated!",
    category=UserWarning,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("langchain.retrievers.self_query").setLevel(logging.INFO)

def run_analysis_pipeline(query: str):
    """Runs RAG: DateResolve -> Decomp & BroadQuery -> ParallelRetrievals -> Rerank -> Aggregate -> FullDoc -> NativeThoughts+Answer."""
    print("\n--- Starting Analysis Pipeline (DateResolve, Decomp+Broad, ParallelRetrieve, Rerank, Aggregate, NativeThoughts) ---")

    current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"Using current date: {current_date_str} for analysis context.")

    if not os.path.exists(VECTOR_STORE_PATH) or not os.listdir(VECTOR_STORE_PATH):
        print(f"Error: Vector store not found or empty at {VECTOR_STORE_PATH}.")
        print("Please run 'python build_vector_store.py' first.")
        return

    try:
        embeddings = get_embedding_function()
    except Exception as e:
        print(f"Failed to initialize embedding model: {e}")
        return

    print(f"Loading pre-built vector store from: {VECTOR_STORE_PATH}")
    try:
        vector_store = FAISS.load_local(
            f"{VECTOR_STORE_PATH}/faiss_index",
            embeddings,
            allow_dangerous_deserialization=True
        )
        print(f"Loaded FAISS vector store with {len(vector_store.index_to_docstore_id)} documents.")
    except Exception as e:
        print(f"Error loading vector store: {e}")
        print(f"Ensure the store was built correctly and collection name ('{VECTOR_STORE_PATH}') matches.")
        return

    # The SelfQueryRetriever will be created inside create_rag_chain
    # So, we don't call get_retriever here for the main RAG setup.
    # retriever = get_retriever(vector_store, RETRIEVER_TOP_K)
    # if not retriever:
    #     print("Failed to create a basic retriever. Cannot proceed.")
    #     return

    try:
        from config import SMALL_MODEL_NAME, LARGE_MODEL_NAME

        # Pro model for the final, polished answer
        main_llm_for_answer = get_llm(
            temperature=0.7,
            include_thoughts_in_response=True,
            model_name=LARGE_MODEL_NAME,
        )

        # Fast & cheaper Flash model for all intermediate steps
        reranking_llm = get_llm(temperature=0.3, model_name=SMALL_MODEL_NAME)
        decomposition_llm = get_llm(temperature=0.4, model_name=SMALL_MODEL_NAME)
        broad_query_llm = get_llm(temperature=0.4, model_name=SMALL_MODEL_NAME)
        filter_generation_llm = get_llm(temperature=0.0, model_name=SMALL_MODEL_NAME)
    except Exception as e:
        print(f"Failed to initialize LLMs: {e}")
        return

    try:
        rag_chain = create_rag_chain(
            vector_store, main_llm_for_answer, reranking_llm, 
            decomposition_llm, filter_generation_llm, broad_query_llm
        )
    except Exception as e:
        print(f"Failed to create RAG chain: {e}")
        traceback.print_exc()
        return

    print(f"\nInvoking RAG chain with query: '{query}'")
    final_answer = None
    reasoning_trail = None
    analyzed_docs_metadata = []
    try:
        invoke_input = {"question": query, "current_date": current_date_str} 
        chain_output = rag_chain.invoke(invoke_input)

        if isinstance(chain_output, dict):
            final_answer = chain_output.get('final_answer', 'Error: Final answer not found')
            reasoning_trail = chain_output.get('reasoning_trail', 'Error: Reasoning trail not found or not enabled.')
            analyzed_docs_metadata = chain_output.get('analyzed_metadata', [])
            
            print("\n--- Reasoning Trail from API --- (if present)")
            print(reasoning_trail if reasoning_trail else "(No reasoning trail content provided by API or parsing)")
            print("--------------------------------")
            print("\n--- Final Analysis Result --- (from dict)")
            print(final_answer)
            print("---------------------------")
            
            if analyzed_docs_metadata:
                print(f"--- Metadata for {len(analyzed_docs_metadata)} Documents Used in Final Context ---")
                for meta_item in analyzed_docs_metadata:
                    # Assuming 'content' in meta_item is the full fetched content
                    # original_chunk_content = meta_item.get('original_chunk_page_content', '[Chunk not available]')[:100]
                    print(f"  - Title: {meta_item.get('title')}, MongoID: {meta_item.get('mongo_id')}, Type: {meta_item.get('doc_type')}, Date: {meta_item.get('date')}")
                    # print(f"    Initial chunk for reranking (first 100 chars): {original_chunk_content}...")
            else:
                print("--- No specific document metadata returned from chain for final context ---")
        else:
             print("Warning: Chain output was not a dictionary.")
             # Attempt to treat the whole output as the answer if it's a string
             final_answer = str(chain_output) if isinstance(chain_output, str) else "Error: Unexpected output format."
             reasoning_trail = "(Chain output was not a dict, reasoning trail not parsed)"
             analyzed_docs_metadata = []
             print("\n--- Reasoning Trail from API --- (if present)")
             print(reasoning_trail)
             print("--------------------------------")
             print("\n--- Final Analysis Result --- (fallback)")
             print(final_answer)
             print("---------------------------\n")

    except Exception as e:
        print(f"Error during RAG chain invocation: {e}")
        traceback.print_exc()
        return

    if final_answer is None or final_answer.startswith("Error:"):
        print("Error: Analysis generation failed or produced no valid answer.")
        # Optionally, you could still try to generate PDF with whatever info was gathered
        # For now, let's return if the answer is clearly an error or None
        return

    # Use final_answer for PDF generation, now also passing current_date_str for consistency if needed
    generation_date_for_pdf = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # This is the PDF generation timestamp
    create_pdf(
        query=query,
        generation_date=generation_date_for_pdf,
        analysis_result=final_answer, 
        analyzed_docs=analyzed_docs_metadata,
        filename=PDF_OUTPUT_FILENAME,
        reasoning_trail=reasoning_trail,
        current_date_for_analysis=current_date_str # New optional param for PDF
    )

    # After generating the PDF, attempt to send it via email if SMTP settings are configured
    try:
        from config import (
            EMAIL_SMTP_SERVER,
            EMAIL_SMTP_PORT,
            EMAIL_USERNAME,
            EMAIL_PASSWORD,
            EMAIL_SENDER,
            EMAIL_RECIPIENTS,
        )
        from email_utils import send_email_with_attachment

        # Only proceed if essential SMTP settings and at least one recipient are provided
        if (
            EMAIL_SMTP_SERVER
            and EMAIL_USERNAME
            and EMAIL_PASSWORD
            and EMAIL_RECIPIENTS
        ):
            recipients_list = [addr.strip() for addr in EMAIL_RECIPIENTS.split(",") if addr.strip()]

            if not recipients_list:
                print("Email not sent: EMAIL_RECIPIENTS is set but no valid recipients were found.")
            else:
                email_subject = (
                    f"Newsletter: {query[:60]}..." if len(query) > 60 else f"Newsletter: {query}"
                )
                email_body = (
                    f"Hello,\n\nPlease find attached the latest newsletter generated on {generation_date_for_pdf}.\n\nBest regards,\nMaritime Agent"
                )

                send_email_with_attachment(
                    subject=email_subject,
                    body=email_body,
                    to_emails=recipients_list,
                    attachment_path=PDF_OUTPUT_FILENAME,
                    smtp_server=EMAIL_SMTP_SERVER,
                    smtp_port=EMAIL_SMTP_PORT,
                    smtp_username=EMAIL_USERNAME,
                    smtp_password=EMAIL_PASSWORD,
                    sender_email=EMAIL_SENDER,
                    use_tls=EMAIL_SMTP_PORT != 465,  # Heuristic: port 465 often implies implicit SSL
                )
                print("Newsletter sent successfully via email.")
        else:
            print("Email not sent: Missing SMTP configuration in environment variables.")
    except Exception as email_error:
        print(f"Failed to send email: {email_error}")

    print("\n--- Analysis Pipeline Finished ---")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = "Write a newsletter for the marketing department of Kongsberg Maritime about how the shipping industry has evolved in the past couple of years, globally and in the Nordics."
        # user_query = "What are the latest developments in autonomous shipping in the Nordics? Also include info on sustainable maritime fuels."
        print(f"No query provided, using default: '{user_query}'")

    from config import GEMINI_API_KEY
    if GEMINI_API_KEY:
         run_analysis_pipeline(user_query)
    else:
         print("Pipeline cannot run because GEMINI_API_KEY is not set.") 