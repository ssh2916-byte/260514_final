import hashlib
from dataclasses import dataclass

import chromadb
import httpx
import streamlit as st
from bs4 import BeautifulSoup
from openai import OpenAI


@dataclass
class DocumentChunk:
    id: str
    text: str
    url: str
    sap_version: str = ""


def get_chroma_collection():
    if "chroma_client" not in st.session_state:
        st.session_state["chroma_client"] = chromadb.EphemeralClient()
    client = st.session_state["chroma_client"]
    return client.get_or_create_collection("sap_docs")


def crawl_and_chunk(url: str, chunk_size: int = 512, overlap: int = 50) -> list[DocumentChunk]:
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    except Exception:
        return []

    words = text.split()
    step = max(chunk_size - overlap, 1)
    chunks = []
    for i in range(0, len(words), step):
        chunk_words = words[i : i + chunk_size]
        if len(chunk_words) < 50:
            continue
        chunk_text = " ".join(chunk_words)
        chunk_id = hashlib.sha256(f"{url}:{i}".encode()).hexdigest()[:16]
        chunks.append(DocumentChunk(id=chunk_id, text=chunk_text, url=url))
    return chunks


def index_url(url: str, status_callback=None) -> int:
    collection = get_chroma_collection()
    oai = OpenAI(api_key=st.session_state["openai_api_key"])

    chunks = crawl_and_chunk(url)
    if not chunks:
        return 0

    if status_callback:
        status_callback(f"임베딩 생성 중... ({len(chunks)} 청크)")

    texts = [c.text for c in chunks]
    all_embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        emb = oai.embeddings.create(input=batch, model="text-embedding-3-small")
        all_embeddings.extend(e.embedding for e in emb.data)

    existing = collection.get(ids=[c.id for c in chunks])
    existing_ids = set(existing["ids"])

    new_chunks = [c for c in chunks if c.id not in existing_ids]
    new_embeddings = [all_embeddings[i] for i, c in enumerate(chunks) if c.id not in existing_ids]

    if new_chunks:
        collection.add(
            ids=[c.id for c in new_chunks],
            embeddings=new_embeddings,
            documents=[c.text for c in new_chunks],
            metadatas=[{"url": c.url, "sap_version": c.sap_version} for c in new_chunks],
        )

    return len(new_chunks)
