# Maritime Agent

RAG assistant-agent-researcher for maritime market intelligence -- a solution to a course challenge provided by Kongsberg Maritime. This project has been made, designed, and presented by Darijus Seporaitis, Ville Palola, Aki Koppinen, Keito Sadamatsu, Tzu-chun Wang

---
## 1. High-Level Architecture

1. **Scraper**
   • Collects news / patent / research pages and stores raw text plus metadata.
2. **Vector Builder**
   • Splits documents → encodes with sentence-transformer embeddings → persists FAISS index.
3. **Analysis Pipeline**
   • Date-aware query decomposition, broad-query sweep, parallel retrieval, LLM rerank, full-doc fetch, Gemini reasoning, PDF export, and optional SMTP e-mail for autonomous newsletters.
4. **API Layer**
   • FastAPI endpoint exposing the pipeline to a web UI / external callers.
5. **Utilities**
   • PDF generator, SMTP helper, vector-store and prompt helpers.

Graphical flow:
```
User Query
   │
   ▼
┌──────────────────────┐
│ 1️⃣ Query Decomposition (flash) │  ← splits complex question into sub-queries + broad sweep
└──────────────────────┘
   │ sub-queries
   ▼
┌──────────────────────┐
│ 2️⃣ Parallel Retrieval (FAISS) │  ← each sub-query + broad query hits the vector index
└──────────────────────┘
   │ chunks
   ▼
┌──────────────────────┐
│ 3️⃣ LLM Rerank (flash) │  ← filters chunks to those truly relevant
└──────────────────────┘
   │ curated chunks
   ▼
┌──────────────────────────────┐
│ 4️⃣ Full-Document Fetch (Mongo) │  ← swap chunks for full articles / patents
└──────────────────────────────┘
   │ context
   ▼
┌──────────────────────┐
│ 5️⃣ Gemini-Pro Answer │  ← crafts final answer + thoughts
└──────────────────────┘
   │
   ▼
PDF Report → optional SMTP Email
```

**Key points**
• Steps 1-4 run on the fast Flash model for cost/speed; only the final answer (step 5) uses the higher-quality Pro model.
• Vector search uses FAISS on sentence-transformer embeddings; metadata filters are built via LangChain's Self-Query retriever.
• Reranking LLM keeps only the chunks that actually answer the user's intent, cutting noise.
• Full documents are pulled from MongoDB so the final prompt has complete context, not snippets.
• The resulting answer and citations are laid out as a PDF and optionally mailed as a newsletter.

---
## 2. Command Reference
| Command | Purpose |
|---------|---------|
| `python run_scrape.py` | Scrape latest sources into MongoDB |
| `python build_vector_store.py` | Encode docs & update FAISS index |
| `python main.py "<query>"` | Generate PDF (and send e-mail) |
| `uvicorn main_api:app --reload` | Run FastAPI endpoint (localhost:8000) for UI access (see section 6.)|

---
## 3. Project Structure
```
.
├── build_vector_store.py   # create/update FAISS index
├── main.py                # end-to-end analysis pipeline
├── main_api.py            # FastAPI wrapper
├── email_utils.py         # SMTP helper
├── pdf_generator.py       # pretty PDF export
├── vector_store_utils.py  # embedding + retriever helpers
├── llm_interface.py       # all LangChain chains & Gemini calls
└── scraper/               # site/patent/research scraper
```
See source files for inline docs.

---
## 4. Tips & Troubleshooting
• Missing `GEMINI_API_KEY` ⇒ pipeline aborts early (config check).  
• Gmail `534-5.7.9` error ⇒ App-Password not enabled or wrong port.  
• Large queries? Adjust `RETRIEVER_TOP_K` in `config.py`.

---
## 5. Setup

### 5.1 Prerequisites
• Python 3.11 +  (venv highly recommended)
• A Google Gemini API key
• (Optional) A Gmail account + App-Password if you want automatic e-mail notifications.

### 5.2 Installation
```bash
git clone <repo>
cd maritime-agent
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5.3 Environment Variables (`.env`)
```env
# ------------ CORE ------------
GEMINI_API_KEY=yourGeminiKeyHere
MONGO_URI="mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority"

# ------------ SMTP  (optional) ------------
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=yourgmail@gmail.com
EMAIL_PASSWORD=16charAppPassword         # REMOVE SPACES from Google's 4×4 format
EMAIL_SENDER=yourgmail@gmail.com         # optional – defaults to EMAIL_USERNAME
EMAIL_RECIPIENTS=yourgmail@gmail.com     # comma-separate for multiple
```
Google app-passwords appear with spaces, like `abcd efgh ijkl mnop`; remove spaces or wrap the value in quotes.

### 5.4 Build the Vector Index (first-time / when data changes)
```bash
python build_vector_store.py
```

### 5.5 Run an Analysis & Send Newsletter
```bash
python main.py "Write a newsletter on …"
# ➜ analysis_report_langchain.pdf produced & sent via email if SMTP vars are set
```



## 6. UI

Find UI implementation here: https://github.com/Finsaki/quick-construct-toolkit-57

Run FastAPI server to interact with UI with

```
uvicorn main_api:app --reload
```

The FastAPI server runs on port 8000 by default, UI runs on port 8080 by default