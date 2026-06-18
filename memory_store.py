import chromadb
import uuid
from chromadb.utils import embedding_functions

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