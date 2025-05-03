# Maritime Agent

Retrieval-Augmented Generation (RAG) system for analyzing maritime documents using Google Gemini.

## Setup

1.  **Clone Repository:**
    ```bash
    git clone <repository-url>
    cd maritime-agent
    ```
2.  **Install Dependencies:** Requires Python 3.x.
    ```bash
    pip install -r requirements.txt
    ```
    *(Optional)* For GPU-accelerated embeddings, install PyTorch with CUDA support corresponding to your hardware via the [PyTorch website](https://pytorch.org/get-started/locally/). The system automatically detects and utilizes CUDA if available.
3.  **Configure API Key:**
    *   Create a `.env` file in the project root.
    *   Add the Gemini API key:
        ```env
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        ```
    *   Obtain an API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Usage

1.  **Build Vector Store:** Process source documents (`blog_posts.csv`) and generate embeddings. This step is required only once or when source data changes.
    ```bash
    python build_vector_store.py
    ```
    This command populates the `./chroma_db_store` vector database and creates `original_doc_lookup.pkl`.

2.  **Run Analysis:** Execute analysis with a query.
    ```bash
    python main.py "<Your query text>"
    ```
    *   Replace `<Your query text>` with the analysis query.
    *   Omitting the query uses a default value.
    *   Output is saved to `analysis_report_langchain.pdf`.

Refer to console output for error diagnostics.