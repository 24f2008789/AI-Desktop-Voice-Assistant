import os
import uuid
import chromadb
import hashlib
from pypdf import PdfReader
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

client = chromadb.PersistentClient(path="./chroma_db")

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = client.get_or_create_collection(
    name="assistant_memory",
    embedding_function=embedding_fn
)

pdf_collection = client.get_or_create_collection(
    name="pdf_rag",
    embedding_function=embedding_fn
)

def save_memory(memory_text):

    existing = collection.query(
        query_texts=[memory_text],
        n_results=1
    )

    docs = existing["documents"][0]

    if docs:
        if docs[0].lower() == memory_text.lower():
            return

    collection.add(
        ids=[str(uuid.uuid4())],
        documents=[memory_text]
    )

def retrieve_memories(query):

    results = collection.query(
        query_texts=[query],
        n_results=5
    )

    docs = results["documents"][0]

    return "\n".join(docs)

def _file_id(pdf_path: str) -> str:
    """Stable ID for a file based on its absolute path."""
    abs_path = os.path.abspath(pdf_path)
    return hashlib.md5(abs_path.encode()).hexdigest()

def load_pdf_to_chroma(pdf_path: str):
    """
    Loads a PDF into ChromaDB WITHOUT deleting other PDFs.
    If the same file is loaded again, its old chunks are replaced (not duplicated).
    """
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File not found: {pdf_path}")

        if not pdf_path.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

        filename = os.path.basename(pdf_path)
        file_id = _file_id(pdf_path)

        # ── Remove OLD chunks of THIS SAME FILE ONLY (not all files) ──
        existing = pdf_collection.get(
            where={"file_id": file_id},
            include=[]
        )
        if existing["ids"]:
            pdf_collection.delete(ids=existing["ids"])
            print(f"Replaced {len(existing['ids'])} old chunks for '{filename}'")

        # ── Read PDF ──
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            raise ValueError("No text found inside PDF.")

        # ── Split into chunks ──
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150
        )
        chunks = splitter.split_text(text)

        if not chunks:
            raise ValueError("No chunks created.")

        # ── Store with metadata so we know which file each chunk is from ──
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {"file_id": file_id, "filename": filename}
            for _ in chunks
        ]

        pdf_collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )

        print(f"Loaded {len(chunks)} chunks from '{filename}' into ChromaDB.")
        return True

    except Exception as e:
        print(f"PDF Loading Error: {e}")
        return False
    
def retrieve_pdf_context(query: str, top_k: int = 4):
    """
    Retrieves the most relevant chunks across ALL loaded PDFs.
    Returns context with filename labels so the LLM knows the source.
    """
    try:
        if not query.strip():
            return ""

        results = pdf_collection.query(
            query_texts=[query],
            n_results=top_k
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return ""

        # Label each chunk with its source filename
        labeled_chunks = []
        for doc, meta in zip(documents, metadatas):
            filename = meta.get("filename", "unknown.pdf") if meta else "unknown.pdf"
            labeled_chunks.append(f"[From {filename}]\n{doc}")

        return "\n\n".join(labeled_chunks)

    except Exception as e:
        print(f"Retrieval Error: {e}")
        return ""


def list_loaded_pdfs():
    """Returns list of unique PDF filenames currently in the store."""
    try:
        all_data = pdf_collection.get(include=["metadatas"])
        filenames = set()
        for meta in all_data.get("metadatas", []):
            if meta and "filename" in meta:
                filenames.add(meta["filename"])
        return sorted(filenames)
    except Exception as e:
        print(f"List PDFs Error: {e}")
        return []


def delete_pdf_from_chroma(filename_or_path: str):
    """Delete a specific PDF's chunks by filename or path."""
    try:
        file_id = _file_id(filename_or_path) if os.path.sep in filename_or_path else None

        if file_id:
            existing = pdf_collection.get(where={"file_id": file_id}, include=[])
        else:
            existing = pdf_collection.get(where={"filename": filename_or_path}, include=[])

        if existing["ids"]:
            pdf_collection.delete(ids=existing["ids"])
            print(f"Deleted {len(existing['ids'])} chunks")
            return True
        return False
    except Exception as e:
        print(f"Delete Error: {e}")
        return False