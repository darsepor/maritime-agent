# llm_interface.py
from operator import itemgetter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
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

def get_full_docs_and_metadata(retrieved_chunks: list[Document], original_doc_lookup: dict) -> dict:
    """Retrieves full doc text & metadata using chunks and lookup. Returns dict."""
    print(f"Retrieved {len(retrieved_chunks)} chunks. Fetching full documents and metadata...")
    unique_docs_data = {}
    # Use a set to track unique lookup keys added
    added_keys = set()

    for chunk in retrieved_chunks:
        title = chunk.metadata.get('title', 'N/A')
        date = chunk.metadata.get('date', 'N/A')
        lookup_key = (title, date)

        # Only process if we haven't added this original doc yet
        if lookup_key in original_doc_lookup and lookup_key not in added_keys:
            content, url = original_doc_lookup[lookup_key]
            doc_data = {
                'title': title,
                'date': date.strip(), # Clean up whitespace from date
                'url': url,
                'content': content
            }
            unique_docs_data[lookup_key] = doc_data
            added_keys.add(lookup_key)
            print(f"  - Added full document: Title='{title}', Date='{date.strip()}'")
        elif lookup_key not in original_doc_lookup:
            print(f"  - Warning: Could not find original document for chunk: Title='{title}', Date='{date}'")

    # Combine the unique full document texts for context
    context_strings = [
        "\n\n--- NEXT DOCUMENT (Title: {title}, Date: {date}) ---\n\n{content}".format(
            title=data['title'], date=data['date'], content=data['content']
        ) for data in unique_docs_data.values()
    ]
    context_string = "".join(context_strings)

    analyzed_metadata = list(unique_docs_data.values()) # List of dicts for PDF

    if not context_string:
        print("Warning: No full documents could be fetched for context.")
        print("Falling back to using chunk text for context.")
        context_string = "\n\n---\n\n".join([chunk.page_content for chunk in retrieved_chunks])
        # Provide minimal metadata based on chunks if possible
        analyzed_metadata = [{'title': c.metadata.get('title', 'N/A'), 'date': c.metadata.get('date', 'N/A').strip(), 'url': c.metadata.get('url', '#'), 'content': '[Chunk Content Only]'} for c in retrieved_chunks]


    print(f"Combined {len(unique_docs_data)} unique full documents for context.")
    return {"context_str": context_string, "analyzed_metadata": analyzed_metadata}

def create_rag_chain(retriever, llm):
    """Creates RAG chain outputting analysis and metadata."""
    template = """
    You are an assistant tasked with analyzing resources related to the maritime industry in the Nordic region.
    Use the following full documents (retrieved based on query relevance) to answer the question.
    If you don't know the answer based on these posts, just say that you don't know.
    Keep the answer concise and directly related to the question. But do explore and be creative if seems appropriate.

    CONTEXT:
    {context} # This will be the full documents

    QUESTION:
    {question}

    ANSWER:
    """
    prompt = ChatPromptTemplate.from_template(template)

    retrieve_chunks = itemgetter("question") | retriever

    # Renamed function and updated lambda
    create_context_and_metadata = RunnableLambda(
        lambda x: get_full_docs_and_metadata(x["retrieved_chunks"], x["original_doc_lookup"]),
        name="FetchFullDocsAndMetadata"
    )

    # Define the final chain structure
    rag_chain = (
        RunnableParallel(
            {
                "retrieved_chunks": retrieve_chunks,
                "question": itemgetter("question"),
                "original_doc_lookup": itemgetter("original_doc_lookup"),
            }
        )
        # Step 2: Generate context string and metadata list
        | RunnableParallel(
            {
                "result_from_fetch": create_context_and_metadata,
                "question": itemgetter("question"), # Pass question through
            }
        )
        # Step 3: Prepare input for the LLM prompt and pass metadata along
        | RunnableParallel(
            {
                "prompt_input": RunnableLambda(lambda x: {"context": x["result_from_fetch"]["context_str"], "question": x["question"]}),
                "analyzed_metadata": RunnableLambda(lambda x: x["result_from_fetch"]["analyzed_metadata"])
            }
        )
        # Step 4: Call the LLM and combine its output with the metadata
        | RunnableParallel(
            {
                "analysis": itemgetter("prompt_input") | prompt | llm | StrOutputParser(),
                "analyzed_metadata": itemgetter("analyzed_metadata") # Pass metadata through
            }
        )
    )

    print("RAG chain (outputting dict: analysis, analyzed_metadata) created.")
    return rag_chain 