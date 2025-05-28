from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from subprocess import run
from pymongo import MongoClient
import os

app = FastAPI()

MONGO_URI = "your_mongodb_connection_string"
DB_NAME = "your_database"
COLLECTION_NAME = "your_collection"

@app.get("/")
def home():
    return {"message": "API is running"}

@app.post("/run-scraper")
def run_scraper():
    result = run(["python", "run_scrape.py"])
    return {"status": "completed", "return_code": result.returncode}

@app.post("/build-vector-store")
def build_vector_store():
    # You could optionally pull from MongoDB and write to a new .csv here
    result = run(["python", "build_vector_store.py"])
    return {"status": "vector store built", "return_code": result.returncode}

@app.post("/run-analysis")
def run_analysis(query: str = Form(...)):
    result = run(["python", "main.py", query])
    return {"status": "analysis complete", "pdf": "/get-report"}

@app.get("/get-report")
def get_report():
    return FileResponse("analysis_report_langchain.pdf", filename="maritime_analysis.pdf", media_type='application/pdf')
