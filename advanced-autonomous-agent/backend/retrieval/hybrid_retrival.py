from typing import List , Dict
from .bm25_retriever import BM25Retriever
from .reranker import JobReranker
from .fusion import ReciprocalRank
import numpy as np
import structlog

logger = structlog.get_logger()

class HybridRetriever:
    def __init__(self, embedding_model, reranker_model):

        logger.warning(
            f"Hybrid retriever embedding model type {type(embedding_model)}"
        )

        self.embedding_model = embedding_model
        self.bm25_retriever = BM25Retriever()
        self.job_reranker =  JobReranker(
            reranker_model
        )
        self.reciprocal_rank = ReciprocalRank()
    
    def dense_retrieve(self, resume_text: str, user_id: str, jobs: List[Dict], top_k: int = 50):

        try:
            resume_embedding = self.embedding_model.encode(
                resume_text,
                convert_to_numpy=True
            )
            if resume_embedding is None:
                logger.warning(f"No resume embeddigs found for {user_id}")

            job_texts = []

            for job in jobs:

                skills = ", ".join(job.get("skills", []))
                
                texts = f"""

                Title: {job.get("title", "")}
                Skills: {skills}
                Company: {job.get("company", "")}
                Location: {job.get("location", "")}
                Experience: {job.get("experience", "")}
                Description: {job.get("description", "")[:1000]}
                """

                job_texts.append(texts)
            
            job_embedding = self.embedding_model.encode(
                job_texts,
                convert_to_numpy=True
            )
            if job_embedding is None:
                logger.warning(f"No job embeddings found for: {user_id}")

            # Calculating Cosine similarity
            similarity = np.dot(
                job_embedding,
                resume_embedding
            ) / (
                np.linalg.norm(job_embedding, axis=1) * np.linalg.norm(resume_embedding)
            )

            top_k = min(top_k, len(jobs))
            top_indices = np.argsort(similarity)[-top_k:][::-1]


            results = []

            for idx in top_indices:

                job = jobs[idx].copy()

                job["dense_score"] = float(
                    similarity[idx]
                )

                results.append(job)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in dense retrieval: {e}")
            return []

    def retrieve(self, resume_text: str, user_id: str, jobs: List[Dict], top_k: int = 30):

        dense_results = self.dense_retrieve(
            resume_text,
            user_id,
            jobs,
            top_k
        )

        bm25_results = self.bm25_retriever.retrieve(
            resume_text,
            user_id,
            jobs,
            top_k
        )

        fused_results = self.reciprocal_rank.fuse(
            dense_results,
            bm25_results
        )

        reranker_results = self.job_reranker.reranker(
           resume_text,
           fused_results,
           top_k=20
        )

        return reranker_results





    