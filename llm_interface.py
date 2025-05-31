# llm_interface.py
from operator import itemgetter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel, RunnableBranch
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.messages import AIMessage # For inspecting AIMessage content
from langchain_core.documents import Document
from langchain.chains.query_constructor.base import AttributeInfo # For SelfQueryRetriever
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores.faiss import FAISS as FAISSVectorStore
from faiss_translator import FaissTranslator
import json # For robust JSON parsing
import datetime # For current date
from prompts import (
    QUERY_DECOMPOSITION,
    BROAD_QUERY_GENERATION,
    RERANK_YES_NO,
    FINAL_ANSWER_TEMPLATE,
)

from config import GEMINI_MODEL_NAME, GEMINI_API_KEY, MONGO_URI, MONGO_DATABASE_NAME, RETRIEVER_TOP_K
from data_base import MongoHandler
# Attempt to import keyword lists from processor.py
# This is a simple way; for complex projects, consider a shared config or constants file.
try:
    from processor import ArticleMetadataProcessor
    processor_instance = ArticleMetadataProcessor()
    # Using all keywords now
    ALL_KONGSBERG_KEYWORDS = sorted(list(set(processor_instance.kongsberg_keywords + processor_instance.kongsberg_patents_keywords)))
    ALL_MARITIME_KEYWORDS = sorted(list(set(processor_instance.maritime_keywords + processor_instance.maritime_patent_keywords)))
except ImportError:
    print("Warning: processor.py not found or ArticleMetadataProcessor has changed. Using generic keyword descriptions.")
    ALL_KONGSBERG_KEYWORDS = ["kongsberg", "autonomous", "defense", "remote weapon system", "sonar system"]
    ALL_MARITIME_KEYWORDS = ["ship", "port", "vessel", "navigation", "engine", "autonomous ship", "hull", "IMO"]

def get_llm(temperature: float = 0.7, include_thoughts_in_response: bool = False):
    """Initializes the Gemini LLM with configurable temperature and include_thoughts."""
    print(f"Initializing LLM: {GEMINI_MODEL_NAME} with temp: {temperature}, include_thoughts: {include_thoughts_in_response}")
    try:
        model_params = {
            "model": GEMINI_MODEL_NAME,
            "google_api_key": GEMINI_API_KEY,
        }
        # For the main LLM (temp 0.7), try with minimal params first.
        # For other LLMs, retain their specific configurations.
        if temperature == 0.7:
            print("Using simplified model_params for main LLM (temp 0.7) for testing.")
            if include_thoughts_in_response:
                model_params["include_thoughts"] = True
                model_params["convert_system_message_to_human"] = True
        else:
            model_params["temperature"] = float(temperature)
            model_params["convert_system_message_to_human"] = True
            if include_thoughts_in_response:
                model_params["include_thoughts"] = True
        
        llm = ChatGoogleGenerativeAI(**model_params)
        print("LLM initialized.")
        return llm
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        raise

def create_query_decomposition_chain(llm):
    """Creates a chain to decompose a user query into sub-queries."""
    prompt = ChatPromptTemplate.from_template(QUERY_DECOMPOSITION)
    
    # Attempt to parse JSON, with fallback for malformed JSON
    def robust_json_parser(s: str):
        try:
            return JsonOutputParser().parse(s)
        except Exception as e:
            print(f"Warning: JSON parsing failed for sub-query generation: {e}. Output: '{s}'. Returning raw string in list.")
            return [s] # Fallback to the raw string as a single query, hoping it's the original query or usable

    return prompt | llm | StrOutputParser() | RunnableLambda(robust_json_parser)

def create_broad_query_generation_chain(llm):
    """Creates a chain to generate a single, broader query for a general sweep."""
    prompt = ChatPromptTemplate.from_template(BROAD_QUERY_GENERATION)
    return prompt | llm | StrOutputParser()

def format_docs_from_chunks(docs: list[Document]) -> str:
    """Helper function to format retrieved document CHUNKS for the prompt context if full doc retrieval fails."""
    formatted_docs = []
    for i, doc in enumerate(docs):
        title = doc.metadata.get('title', 'N/A')
        date = doc.metadata.get('date', 'N/A')
        source_info = f"Document {i+1} (Title: {title}, Date: {date})"
        if 'patent_code' in doc.metadata and doc.metadata['patent_code']:
            source_info += f" Patent: {doc.metadata['patent_code']}"
        formatted_docs.append(f"--- {source_info} ---\n{doc.page_content}")
    return "\n\n".join(formatted_docs)

def get_full_docs_and_metadata_from_mongo(retrieved_chunks: list[Document]) -> dict:
    """Retrieves full doc text & metadata from MongoDB using mongo_id from chunks."""
    if not retrieved_chunks:
        return {"context_str": "", "analyzed_metadata": []}
        
    print(f"Received {len(retrieved_chunks)} chunks for full doc processing. Fetching from MongoDB...")
    mongo_handler = MongoHandler(MONGO_URI, MONGO_DATABASE_NAME)
    unique_docs_data = {}
    added_mongo_ids = set()

    for chunk in retrieved_chunks:
        mongo_id = chunk.metadata.get('mongo_id')
        if not mongo_id or mongo_id in added_mongo_ids: continue
        domain = chunk.metadata.get('doc_type', "news")
        full_doc_data = mongo_handler.get_document_by_id(domain, mongo_id)
        doc_display_data = {}
        if full_doc_data:
            content = full_doc_data.get('text', chunk.page_content)
            doc_display_data = {k: v for k, v in full_doc_data.items() if k != "_id"}
            doc_display_data['content'] = content
        else: # Fallback to chunk data if full doc not found
            print(f"  - Warning: Full doc not found for mongo_id: {mongo_id}. Using chunk data.")
            doc_display_data = {k: v for k, v in chunk.metadata.items()}
            doc_display_data['content'] = chunk.page_content
        doc_display_data['mongo_id'] = mongo_id # Ensure it's there
        doc_display_data['original_chunk_page_content'] = chunk.page_content
        unique_docs_data[mongo_id] = doc_display_data
        added_mongo_ids.add(mongo_id)

    context_strings = [f"--- DOCUMENT (Title: {d.get('title', 'N/A')}, Date: {d.get('date', 'N/A')}, Type: {d.get('doc_type', 'N/A')}) ---\n{d.get('content', '')}" for d in unique_docs_data.values()]
    context_string = "\n\n".join(context_strings)
    analyzed_metadata = list(unique_docs_data.values())

    if not context_string and retrieved_chunks:
        print("Warning: No full documents context. Falling back to formatted chunks.")
        # Simplified fallback from previous version
        context_string = format_docs_from_chunks(retrieved_chunks)
        analyzed_metadata = [c.metadata for c in retrieved_chunks]

    print(f"Combined {len(unique_docs_data)} unique documents/chunks for context.")
    return {"context_str": context_string, "analyzed_metadata": analyzed_metadata}

def create_reranking_llm_chain(llm):
    """Creates a chain that uses an LLM to decide if a document is relevant to a query."""
    prompt = ChatPromptTemplate.from_template(RERANK_YES_NO)
    return prompt | llm | StrOutputParser()

def rerank_documents_with_llm(original_query: str, documents: list[Document], llm_for_reranking, reranking_chain):
    """Reranks documents based on LLM's assessment of relevance."""
    if not documents:
        return []
    
    print(f"Reranking {len(documents)} documents with LLM for original query: '{original_query}'...")
    reranked_documents = []
    for doc in documents:
        try:
            relevance_assessment = reranking_chain.invoke({"query": original_query, "document_text": doc.page_content})
            print(f"  - Doc (Title: {doc.metadata.get('title', 'N/A')[:30]}...) assessment: {relevance_assessment}")
            if "yes" in relevance_assessment.lower():
                reranked_documents.append(doc)
        except Exception as e:
            print(f"    Error reranking doc: {doc.metadata.get('title', 'N/A')}. Error: {e}")
    print(f"Reranked down to {len(reranked_documents)} documents.")
    return reranked_documents

# Helper to process a single sub-query (or broad query without self-query filters)
def retrieve_and_rerank(query_dict: dict, vector_store, filter_gen_llm, rerank_llm, rerank_chain_instance, document_content_desc, metadata_field_info_list, is_broad_query=False):
    # query in query_dict is now the raw sub-query or broad_query, augmented with current_date prefix just before this call.
    augmented_query_with_date = query_dict["augmented_query_with_date"] 
    original_user_query = query_dict["original_user_query"]
    print(f"\nProcessing for retrieval: '{augmented_query_with_date}' (Broad: {is_broad_query}, from original: '{original_user_query}')")
    if is_broad_query:
        retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVER_TOP_K * 2, "fetch_k": RETRIEVER_TOP_K * 2})
    else:
        # If we're working with a FAISS vector store, plug in our custom translator
        if isinstance(vector_store, FAISSVectorStore):
            translator = FaissTranslator()
            retriever = SelfQueryRetriever.from_llm(
                filter_gen_llm,
                vector_store,
                document_content_desc,
                metadata_field_info_list,
                enable_limit=False,
                search_kwargs={"k": RETRIEVER_TOP_K, "fetch_k": RETRIEVER_TOP_K},
                structured_query_translator=translator,
                verbose=True,
            )
        else:
            retriever = SelfQueryRetriever.from_llm(
                filter_gen_llm,
                vector_store,
                document_content_desc,
                metadata_field_info_list,
                enable_limit=False,
                search_kwargs={"k": RETRIEVER_TOP_K, "fetch_k": RETRIEVER_TOP_K},
                verbose=True,
            )
    try:
        retrieved_chunks = retriever.invoke(augmented_query_with_date)
    except Exception as e:
        print(f"  - Warning: SelfQueryRetriever failed ({e}). Falling back to plain similarity search.")
        fallback_retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVER_TOP_K, "fetch_k": RETRIEVER_TOP_K})
        retrieved_chunks = fallback_retriever.invoke(augmented_query_with_date)
    return rerank_documents_with_llm(original_user_query, retrieved_chunks, rerank_llm, rerank_chain_instance)

def parse_main_llm_output(response_message: AIMessage):
    """Parses the AIMessage from main_llm, separating thoughts and final answer."""
    final_answer_parts = []
    reasoning_trail_parts = []
    # Ensure content is a list, as include_thoughts might make it so
    content_parts = response_message.content
    if isinstance(content_parts, str):
        # If it's a string, no thoughts were embedded by LangChain this way, assume it's all answer
        final_answer_parts.append(content_parts)
    elif isinstance(content_parts, list):
        for part in content_parts:
            if isinstance(part, dict) and part.get("type") == "thinking":
                reasoning_trail_parts.append(part.get("thinking", ""))
            elif isinstance(part, str):
                final_answer_parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text": # Another possible format for text part
                 final_answer_parts.append(part.get("text", ""))
    
    final_answer = "\n".join(filter(None, final_answer_parts)).strip()
    reasoning_trail = "\n---\n".join(filter(None, reasoning_trail_parts)).strip()
    
    if not final_answer and not reasoning_trail and isinstance(response_message.content, str):
        # Fallback if content was string and parsing above didn't catch it as main answer
        final_answer = response_message.content
        
    print(f"\n--- Parsed Main LLM Output ---")
    print(f"Reasoning Trail Retrieved: {'(present)' if reasoning_trail else '(absent)'}")
    # print(f"Reasoning: {reasoning_trail}") # Can be very verbose
    print(f"Final Answer Preview: {final_answer[:100]}...")
    return {"final_answer": final_answer, "reasoning_trail": reasoning_trail}

def create_rag_chain(vector_store, main_llm_for_answer, reranking_llm, decomposition_llm, filter_generation_llm, broad_query_llm):
    """RAG chain: Date-Aware Decomp & BroadQuery -> ParallelRetrievals -> Rerank -> Aggregate -> FullDoc -> NativeThoughts+Answer."""
    
    document_content_description = "News and patent documents related to maritime industry, technology, Nordics."
    max_kw_in_desc = 50
    kongsberg_desc = f"Kongsberg keywords. E.g.: {', '.join(ALL_KONGSBERG_KEYWORDS[:max_kw_in_desc])}. For list matching."
    maritime_desc = f"Maritime keywords. E.g.: {', '.join(ALL_MARITIME_KEYWORDS[:max_kw_in_desc])}. For list matching."
    metadata_field_info = [
        AttributeInfo(name="doc_type", description="Type: 'news' or 'patent'.", type="string"),
        AttributeInfo(name="date", description="Publication date (YYYY-MM-DD). If the query mentions relative dates like 'last year' or 'recent', the LLM creating filters should interpret this based on the current date context provided at the beginning of the query string.", type="string"),
        AttributeInfo(name="title", description="Title.", type="string"),
        AttributeInfo(name="patent_code", description="Patent code if patent.", type="string"),
        AttributeInfo(name="keywords_kongsberg", description=kongsberg_desc, type="list[string]"),
        AttributeInfo(name="keywords_maritime", description=maritime_desc, type="list[string]"),
    ]

    query_decomposition_chain = create_query_decomposition_chain(decomposition_llm)
    broad_query_generation_chain = create_broad_query_generation_chain(broad_query_llm)
    reranking_chain_instance = create_reranking_llm_chain(reranking_llm)

    final_answer_prompt = ChatPromptTemplate.from_template(FINAL_ANSWER_TEMPLATE)

    def aggregate_and_deduplicate_chunks(list_of_chunk_lists):
        all_chunks = []
        seen_mongo_ids = set()
        for chunk_list in list_of_chunk_lists:
            for chunk in chunk_list:
                mongo_id = chunk.metadata.get('mongo_id')
                if mongo_id and mongo_id not in seen_mongo_ids:
                    all_chunks.append(chunk)
                    seen_mongo_ids.add(mongo_id)
                elif not mongo_id: 
                    all_chunks.append(chunk)
        print(f"Aggregated and de-duplicated to {len(all_chunks)} chunks from {sum(len(cl) for cl in list_of_chunk_lists)} initial chunks.")
        return all_chunks

    def parallel_retrieval_step(input_dict):
        sub_queries_list = input_dict["sub_queries_list"]
        broad_query_str = input_dict["broad_query_str"]
        original_user_query = input_dict["original_user_query"]
        current_date_str = input_dict["current_date"] # This is the string like "2024-07-15"
        
        processed_chunk_lists = []
        # Augment sub-queries with current date before sending to retrieve_and_rerank
        for sq_str in sub_queries_list: 
            augmented_sq = f"Current date: {current_date_str}. User query: {sq_str}"
            chunks = retrieve_and_rerank(
                {"query": sq_str, "augmented_query_with_date": augmented_sq, "original_user_query": original_user_query},
                vector_store, filter_generation_llm, reranking_llm, reranking_chain_instance,
                document_content_description, metadata_field_info, is_broad_query=False
            )
            processed_chunk_lists.append(chunks)
        
        # Augment broad query with current date
        augmented_bq = f"Current date: {current_date_str}. User query: {broad_query_str}"
        broad_query_chunks = retrieve_and_rerank(
            {"query": broad_query_str, "augmented_query_with_date": augmented_bq, "original_user_query": original_user_query},
            vector_store, filter_generation_llm, reranking_llm, reranking_chain_instance,
            document_content_description, metadata_field_info, is_broad_query=True
        )
        processed_chunk_lists.append(broad_query_chunks)
        return {"all_retrieved_chunk_lists": processed_chunk_lists, 
                "original_user_query": original_user_query, 
                "current_date": current_date_str}

    rag_chain = (
        # Step 1: Generate sub-queries and broad query. current_date is passed through.
        RunnableParallel({
            "sub_queries_list": itemgetter("question") | query_decomposition_chain,
            "broad_query_str":  itemgetter("question") | broad_query_generation_chain,
            "original_user_query": itemgetter("question"),
            "current_date": itemgetter("current_date") 
        }).with_config(run_name="GenerateSubAndBroadQueries")
        
        # Step 2: Augment queries with date and perform parallel retrieval and reranking
        | RunnableLambda(parallel_retrieval_step).with_config(run_name="AugmentAndParallelRetrieveRerank")
        
        # Step 3: Aggregate and de-duplicate all chunks
        | RunnableLambda(lambda x: {"aggregated_chunks": aggregate_and_deduplicate_chunks(x["all_retrieved_chunk_lists"]), 
                                   "original_user_query": x["original_user_query"],
                                   "current_date": x["current_date"]})
           .with_config(run_name="AggregateAllChunks")
           
        # Step 4: Fetch full documents for the final set of relevant chunks
        | RunnableParallel({
            "result_from_fetch": lambda x: get_full_docs_and_metadata_from_mongo(x["aggregated_chunks"]),
            "original_user_query": itemgetter("original_user_query"),
            "current_date": itemgetter("current_date")
        }).with_config(run_name="FetchFullDocsForAggregated")
        
        # Step 5: Prepare input for the final LLM answer generation
        | RunnableParallel({
            "prompt_input_for_final_answer": lambda x: {"context": x["result_from_fetch"]["context_str"], 
                                                      "question": x["original_user_query"],
                                                      "current_date": x["current_date"]},
            "analyzed_metadata_for_pdf": lambda x: x["result_from_fetch"]["analyzed_metadata"]
        })
        
        # Step 6: Generate final answer (main_llm_for_answer has include_thoughts=True)
        | RunnableParallel({
            "llm_response_with_potential_thoughts": itemgetter("prompt_input_for_final_answer") | final_answer_prompt | main_llm_for_answer,
            "analyzed_metadata": itemgetter("analyzed_metadata_for_pdf")
        })
        
        # Step 7: Parse the LLM response to separate final answer and thoughts
        | RunnableLambda(lambda x: {
            **parse_main_llm_output(x["llm_response_with_potential_thoughts"]),
            "analyzed_metadata": x["analyzed_metadata"]
          }).with_config(run_name="ParseLLMOutputAndThoughts")
    )

    print("RAG chain (DateAwareDecomp+BroadQuery->ParallelRetrieve->Rerank->Aggregate->NativeThoughts) created.")
    return rag_chain 