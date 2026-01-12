import json
import hashlib
import os
import re
import tempfile
import zipfile
import concurrent.futures
import numpy as np
import faiss
import unicodedata

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from config.settings import Config

# === Azure Blob Storage Helpers & Initialization ===
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()  # loads AZURE_STORAGE_CONNECTION_STRING etc.

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "userfiles")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

def blob_exists(blob_name: str) -> bool:
    """Check if a blob exists in the container."""
    blob_client = container_client.get_blob_client(blob_name)
    return blob_client.exists()

def upload_blob_data(blob_name: str, data: bytes):
    """Upload data to a blob (overwriting if it exists)."""
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)
    print(f"Uploaded blob: {blob_name}")

def download_blob_data(blob_name: str) -> bytes:
    """Download data from a blob."""
    blob_client = container_client.get_blob_client(blob_name)
    stream = blob_client.download_blob()
    return stream.readall()

def get_blob_file_base(user_id: str, file_path: str) -> str:
    """
    Determine the base file name to be used in blob paths.
    If the incoming file name already follows one of the two expected patterns
    (e.g. "userIdeasId" or "userIdeasId-reportid"), it will be preserved.
    Otherwise, the user_id is prepended.
    """
    base = os.path.basename(file_path)
    if base.startswith(f"{user_id}-") and base.endswith(".json"):
        return base[:-5]  # remove the '.json'
    else:
        name, _ = os.path.splitext(base)
        return f"{user_id}-{name}"

# === End Blob Helpers ===

class InMemoryDocstore:
    """
    A simple in‑memory wrapper for a dictionary of documents that provides a .search() method.
    """
    def __init__(self, docs: dict):
        self.docs = docs

    def search(self, doc_id):
        if doc_id in self.docs:
            return self.docs[doc_id]
        try:
            converted = int(doc_id)
            if converted in self.docs:
                return self.docs[converted]
        except (ValueError, TypeError):
            pass
        if isinstance(doc_id, int):
            key_str = str(doc_id)
            if key_str in self.docs:
                return self.docs[key_str]
        return None

def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of the given file from blob storage."""
    hasher = hashlib.sha256()
    try:
        file_bytes = download_blob_data(file_path)
        hasher.update(file_bytes)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error computing hash: {e}")
        return ""

def preprocess_json(json_file_path: str) -> list:
    """
    Preprocess JSON files that may have two internal structures:
      - Type 1: with a "summary" key containing a list of entries.
      - Type 2: with keys such as "executive_summary", etc.
    Returns a list of Document objects.
    """
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252']
    try:
        file_bytes = download_blob_data(json_file_path)
    except Exception as e:
        print(f"Error downloading blob for {json_file_path}: {e}")
        return []
    
    for encoding in encodings_to_try:
        try:
            file_text = file_bytes.decode(encoding, errors='replace')
            data = json.loads(file_text)
            documents = []
            
            # --- Type 1 Processing ---
            if isinstance(data.get("summary"), list):
                summary_data = data.get("summary", [])
                for entry in summary_data:
                    category = entry.get("category", "")
                    status = entry.get("status", "")
                    term = entry.get("term", "")
                    url = entry.get("url", "")
                    summary_text = entry.get("summary", "").strip()
                    
                    full_content = (
                        f"Category: {category}\n"
                        f"Status: {status}\n"
                        f"Term: {term}\n\n"
                        f"Summary: {summary_text}"
                    ).strip()
                    # Normalize unicode text
                    full_content = unicodedata.normalize('NFKC', full_content)
                    
                    if full_content and url:
                        metadata = {
                            "source": json_file_path,
                            "url": url,
                            "category": category,
                            "status": status,
                            "term": term,
                            "encoding": encoding
                        }
                        documents.append(Document(page_content=full_content, metadata=metadata))
            
            # --- Type 2 Processing ---
            elif any(key in data for key in ["executive_summary", "problem_validation", "market", "sources"]):
                main_texts = []
                sources_texts = []
                
                for key, value in data.items():
                    if key.lower() == "sources":
                        if isinstance(value, list):
                            sources_texts.append("\n".join(item.strip() for item in value))
                        elif isinstance(value, str):
                            sources_texts.append(value.strip())
                        else:
                            sources_texts.append(str(value))
                        continue
                    if isinstance(value, str):
                        parts = re.split(r'(?i)(?:\*\*Sources:\*\*|Sources:)', value, maxsplit=1)
                        if len(parts) > 1:
                            main_section = parts[0].strip()
                            sources_section = "Sources:" + parts[1].strip()
                            main_texts.append(f"{key.replace('_', ' ').title()}:\n{main_section}")
                            sources_texts.append(sources_section)
                        else:
                            main_texts.append(f"{key.replace('_', ' ').title()}:\n{value.strip()}")
                    else:
                        main_texts.append(f"{key.replace('_', ' ').title()}:\n{json.dumps(value)}")
                
                full_content = "\n\n".join(main_texts)
                full_content = unicodedata.normalize('NFKC', full_content)
                sources_combined = "\n\n".join(sources_texts) if sources_texts else ""
                
                metadata = {"source": json_file_path, "encoding": encoding}
                if sources_combined:
                    metadata["sources"] = unicodedata.normalize('NFKC', sources_combined)
                
                documents.append(Document(page_content=full_content, metadata=metadata))
            else:
                print(f"File format not recognized for file: {json_file_path}")
            
            return documents
        
        except Exception as e:
            print(f"Error with encoding {encoding}: {str(e)}")
            continue
    
    return []

def split_documents(documents: list) -> list:
    """Split documents into smaller chunks for better retrieval."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True
    )
    chunks = []
    for doc in documents:
        if doc.page_content.strip():
            try:
                print("Chunking document...")
                chunks.extend(text_splitter.split_documents([doc]))
            except Exception as e:
                print(f"Error splitting document: {e}")
    return chunks

def check_file_for_changes(file_path: str, user_id: str) -> bool:
    """
    Check if the file (in blob storage) has changed by comparing its hash to the stored hash.
    The hash marker is stored under:
       user_cache/{user_id}/{blob_base}_data_hash.txt
    """
    current_hash = compute_file_hash(file_path)
    blob_base = get_blob_file_base(user_id, file_path)
    blob_hash_name = f"user_cache/{user_id}/{blob_base}_data_hash.txt"
    print("Checking blob:", blob_hash_name)
    
    if blob_exists(blob_hash_name):
        previous_hash = download_blob_data(blob_hash_name).decode("utf-8").strip()
        if current_hash == previous_hash:
            print(f"File has not changed for user {user_id} (file: {file_path}), skipping reprocessing.")
            return False
    
    upload_blob_data(blob_hash_name, current_hash.encode("utf-8"))
    print(f"File has changed for user {user_id} (file: {file_path}), reprocessing.")
    return True

# Global cache for FAISS indexes.
FAISS_INDEX_CACHE = {}

def initialize_retriever(user_id: str, file_path: str):
    """
    Initialize a FAISS-based retriever with Azure OpenAI embeddings.
    Uses a cached FAISS index if available; otherwise, loads (or rebuilds) the index from blob storage.
    The FAISS index blob name is:
       user_cache/{user_id}/faiss_index_{blob_base}.zip
    """
    blob_base = get_blob_file_base(user_id, file_path)
    blob_index_name = f"user_cache/{user_id}/faiss_index_{blob_base}.zip"
    
    # Check if we have a cached FAISS index in memory.
    if blob_index_name in FAISS_INDEX_CACHE:
        print(f"Using cached FAISS index for {blob_index_name}.")
        vectorstore = FAISS_INDEX_CACHE[blob_index_name]
        if hasattr(vectorstore, "as_retriever"):
            return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})
        else:
            return vectorstore
    
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        model="text-embedding-3-large",
        chunk_size=1200
    )
    
    if not check_file_for_changes(file_path, user_id):
        if blob_exists(blob_index_name):
            try:
                print("Loading FAISS index from Azure Blob Storage cache...")
                temp_dir = tempfile.mkdtemp()
                local_zip_path = os.path.join(temp_dir, "faiss_index.zip")
                with open(local_zip_path, "wb") as f:
                    f.write(download_blob_data(blob_index_name))
                with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                vectorstore = FAISS.load_local(
                    temp_dir,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                # Cache the loaded FAISS index in memory.
                FAISS_INDEX_CACHE[blob_index_name] = vectorstore
                if hasattr(vectorstore, "as_retriever"):
                    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})
                else:
                    return vectorstore
            except Exception as e:
                print(f"Error loading FAISS index: {e}, rebuilding index...")
    
    print("Rebuilding FAISS index...")
    vectorstore = rebuild_faiss_index(embeddings, user_id, file_path, blob_index_name)
    if vectorstore:
        # Cache the newly built FAISS index.
        FAISS_INDEX_CACHE[blob_index_name] = vectorstore
        if hasattr(vectorstore, "as_retriever"):
            return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})
        else:
            return vectorstore
    else:
        return None

def rebuild_faiss_index(embeddings, user_id, file_path, blob_index_name):
    """
    Rebuild the FAISS index, zip it, and upload the zip to Azure Blob Storage.
    """
    if not blob_exists(file_path):
        print(f"Error: Blob {file_path} not found.")
        return None

    print(f"Processing documents for user {user_id} using file {file_path}...")
    current_hash = compute_file_hash(file_path)
    preprocessed_docs = preprocess_json(file_path)
    if not preprocessed_docs:
        print(f"No documents found in file {file_path}.")
        return None

    chunked_docs = split_documents(preprocessed_docs)
    if not chunked_docs:
        print(f"No valid document chunks to build FAISS index for user {user_id} and file {file_path}.")
        return None

    try:
        document_texts = [doc.page_content for doc in chunked_docs]
        
        # Log total tokens used (approximate by splitting on whitespace).
        total_tokens = sum(len(text.split()) for text in document_texts)
        print(f"Total tokens used while creating embeddings: {total_tokens}")
        
        print("Computing embeddings in parallel...")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            document_embeddings = list(executor.map(embeddings.embed_query, document_texts))
        document_embeddings = np.array(document_embeddings, dtype=np.float32)

        d = document_embeddings.shape[1]
        print(f"Building HNSW index with dimension {d}...")
        hnsw_index = faiss.IndexHNSWFlat(d, 32)
        hnsw_index.hnsw.efConstruction = 200
        hnsw_index.hnsw.efSearch = 50
        hnsw_index.add(document_embeddings)

        doc_mapping = {i: doc for i, doc in enumerate(chunked_docs)}
        index_to_docstore_id = {i: i for i in range(len(chunked_docs))}
        vectorstore = FAISS(embeddings, hnsw_index, InMemoryDocstore(doc_mapping), index_to_docstore_id)

        temp_dir = tempfile.mkdtemp()
        vectorstore.save_local(temp_dir)

        zip_path = os.path.join(temp_dir, "faiss_index.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == "faiss_index.zip":
                        continue
                    file_path_local = os.path.join(root, file)
                    arcname = os.path.relpath(file_path_local, temp_dir)
                    zipf.write(file_path_local, arcname)

        with open(zip_path, "rb") as f:
            upload_blob_data(blob_index_name, f.read())
        print("FAISS index rebuilt and saved successfully to Azure Blob Storage.")

        blob_base = get_blob_file_base(user_id, file_path)
        blob_hash_name = f"user_cache/{user_id}/{blob_base}_data_hash.txt"
        upload_blob_data(blob_hash_name, current_hash.encode("utf-8"))

        if hasattr(vectorstore, "as_retriever"):
            return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})
        else:
            return vectorstore
    
    except Exception as e:
        print(f"Error building FAISS index for user {user_id} using file {file_path}: {e}")
        return None
