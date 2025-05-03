# llm_interface.py
from operator import itemgetter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document # To access page_content

from config import GEMINI_MODEL_NAME, GEMINI_API_KEY

def get_llm():
    """Initializes the Gemini LLM."""
    print(f"Initializing LLM: {GEMINI_MODEL_NAME}")
    try:
        llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=GEMINI_API_KEY)
        print("LLM initialized.")
        return llm
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        raise # Re-raise the exception to halt execution if LLM fails

def format_docs(docs: list[Document]) -> str:
    """Helper function to format retrieved documents for the prompt context."""
    # Includes title and date from metadata along with the text content
    formatted_docs = []
    for i, doc in enumerate(docs):
        title = doc.metadata.get('title', 'N/A')
        date = doc.metadata.get('date', 'N/A')
        formatted_docs.append(f"--- Document {i+1} (Title: {title}, Date: {date}) ---\n{doc.page_content}")
    return "\n\n".join(formatted_docs)

def get_full_docs_from_chunks(retrieved_chunks: list[Document], original_doc_lookup: dict) -> str:
    """Retrieves full document text using metadata from chunks and the lookup table."""
    print(f"Retrieved {len(retrieved_chunks)} chunks. Fetching full documents...")
    unique_full_docs = {}
    for chunk in retrieved_chunks:
        title = chunk.metadata.get('title', 'N/A')
        date = chunk.metadata.get('date', 'N/A')
        lookup_key = (title, date)
        if lookup_key in original_doc_lookup:
            # Use the lookup key to store content, ensuring uniqueness
            if lookup_key not in unique_full_docs:
                unique_full_docs[lookup_key] = original_doc_lookup[lookup_key]
                print(f"  - Added full document: Title='{title}', Date='{date}'")
        else:
            print(f"  - Warning: Could not find original document for chunk: Title='{title}', Date='{date}'")

    # Combine the unique full document texts
    context_string = "\n\n--- NEXT DOCUMENT ---\n\n".join(unique_full_docs.values())
    if not context_string:
        print("Warning: No full documents could be fetched for context.")
        # Fallback: maybe return chunk text? Or empty string?
        # Returning concatenated chunk text as fallback:
        print("Falling back to using chunk text for context.")
        return "\n\n---\n\n".join([chunk.page_content for chunk in retrieved_chunks])

    print(f"Combined {len(unique_full_docs)} unique full documents for context.")
    return context_string

def create_rag_chain(retriever, llm, original_doc_lookup):
    """Creates the RAG chain that retrieves chunks but uses full docs for context."""
    template = """
    You are an assistant tasked with analyzing blog posts.
    Use the following full blog posts (retrieved based on query relevance) to answer the question.
    If you don't know the answer based on these posts, just say that you don't know.
    Keep the answer concise and directly related to the question.

    CONTEXT:
    {context} # This will be the full documents

    QUESTION:
    {question}

    ANSWER:
    """
    prompt = ChatPromptTemplate.from_template(template)

    # Chain definition using LCEL (LangChain Expression Language)
    rag_chain = (
        # This dictionary passes the question to the retriever and also forwards it
        # along with the original_doc_lookup to the next step.
        {
            "retrieved_chunks": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "original_doc_lookup": itemgetter("original_doc_lookup")
        }
        # Now, take the output dict and process it
        | RunnableLambda(
            lambda x: get_full_docs_from_chunks(x["retrieved_chunks"], x["original_doc_lookup"])
        ).with_config(run_name="FetchFullDocs") # Assign context to the result
        | RunnablePassthrough.assign(question=itemgetter("question")) # Re-add question for the prompt
        | { "context": RunnablePassthrough(), "question": itemgetter("question") } # Format for prompt
        | prompt
        | llm
        | StrOutputParser()
    )

    # We need to invoke this chain slightly differently now,
    # passing the necessary inputs in a dictionary.
    # The run_analysis_pipeline in main.py handles this implicitly
    # by how create_rag_chain is structured, but the underlying invoke needs a dict.

    # Example of how the dictionary is built before the chain internally:
    # invoke_input = {"question": user_query, "original_doc_lookup": original_doc_lookup}

    print("RAG chain (full doc context) created.")
    return rag_chain 