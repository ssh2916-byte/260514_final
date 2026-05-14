import streamlit as st
from openai import OpenAI
from rank_bm25 import BM25Okapi

from pipelines.sap.indexer import get_chroma_collection
from pipelines.sap.preprocessor import ProcessedQuery


class HybridSearcher:
    def search(self, query: ProcessedQuery, top_k: int = 5) -> list[dict]:
        collection = get_chroma_collection()
        if collection.count() == 0:
            return []

        oai = OpenAI(api_key=st.session_state["openai_api_key"])

        q_embed = (
            oai.embeddings.create(input=query.normalized, model="text-embedding-3-small")
            .data[0]
            .embedding
        )

        n_results = min(top_k * 2, collection.count())
        vector_results = collection.query(
            query_embeddings=[q_embed],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        all_data = collection.get(include=["documents", "metadatas"])
        all_ids: list[str] = all_data["ids"]
        all_docs: list[str] = all_data["documents"]
        all_metas: list[dict] = all_data["metadatas"]

        if not all_docs:
            return []

        tokenized = [d.split() for d in all_docs]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = bm25.get_scores(query.normalized.split())

        return self._rrf_merge(vector_results, bm25_scores, all_ids, all_docs, all_metas, top_k)

    def _rrf_merge(
        self,
        vector_results,
        bm25_scores,
        all_ids: list[str],
        all_docs: list[str],
        all_metas: list[dict],
        top_k: int,
        k: int = 60,
    ) -> list[dict]:
        scores: dict[str, float] = {}

        for rank, doc_id in enumerate(vector_results["ids"][0]):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank + 1)

        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)
        for rank, (idx, _) in enumerate(bm25_ranked[: top_k * 2]):
            if idx < len(all_ids):
                doc_id = all_ids[idx]
                scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank + 1)

        id_to_doc = {
            all_ids[i]: {"id": all_ids[i], "text": all_docs[i], "meta": all_metas[i]}
            for i in range(len(all_ids))
        }
        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [id_to_doc[doc_id] for doc_id in sorted_ids if doc_id in id_to_doc]
