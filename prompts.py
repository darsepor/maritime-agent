# prompts.py
"""Central place to hold all LLM prompt text templates used across the pipeline.

Having them here makes it easy to tweak wording / style in one file instead of
searching through many modules.
"""

# ---------------------------------------------------------------------------
# 1. Query decomposition (turn a complex query into 2-3 focused sub-queries)
# ---------------------------------------------------------------------------
QUERY_DECOMPOSITION = (
    "You are an expert query analyzer. Your task is to decompose a potentially "
    "complex user query: '{user_query}' into up to 10 distinct, concise sub-queries "
    "that can be independently researched. Focus on capturing the core "
    "informational needs. If the query is already simple and focused, you can "
    "return it as a single sub-query in the list. Respond ONLY with a valid "
    "JSON list of strings, where each string is a sub-query."
)

# ---------------------------------------------------------------------------
# 2. Broad query generation (one catch-all vector search query)
# ---------------------------------------------------------------------------
BROAD_QUERY_GENERATION = (
    "You are an expert query reformulator. Given the user query: '{user_query}', "
    "reformulate it into a single, slightly broader search query suitable for "
    "a general semantic vector search. It should capture the main essence but "
    "be general enough not to presuppose specific filters. Respond with only "
    "the single reformulated query string."
)

# ---------------------------------------------------------------------------
# 3. Reranking prompt (YES / NO only)
# ---------------------------------------------------------------------------
RERANK_YES_NO = (
    "Query: '{query}'\n" \
    "Chunk: '{document_text}'\n" \
    "Answer with a single word, either YES or NO. Do not add anything else."
)

# ---------------------------------------------------------------------------
# 4. Final answer synthesis
# ---------------------------------------------------------------------------
FINAL_ANSWER_TEMPLATE = (
    "You are an expert maritime industry analyst. Today's date is {current_date}.\n"
    "Using the CONTEXT, answer the USER QUESTION comprehensively. Reference "
    "today's date for recency. If context is insufficient, say so. Structure your "
    "answer clearly.\n\nCONTEXT:\n{context}\n\nUSER QUESTION:\n{question}\n\nFINAL ANSWER:\n"
) 