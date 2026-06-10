from typing import List, Dict
from rank_bm25 import BM25Okapi
import structlog

logger = structlog.get_logger()

class BM25Retriever:
    def __init__(self):
        pass

    def retrieve(self, resume_text: str, user_id: str, jobs: List[Dict], top_k: int = 50):

        try:

            documents = []

            for job in jobs:

                skills = ", ".join(job.get("skills", []))

                text = f"""

                Title: {job.get("title", "")}
                Skills: {skills}
                Company: {job.get("company", "")}
                Location: {job.get("location", "")}
                Experience: {job.get("experience", "")}
                Description: {job.get("description", "")[:1000]}
                """

                documents.append(text.lower().split())

            bm25 = BM25Okapi(documents)
            query_tokens = resume_text.lower().split()
            scores = bm25.get_scores(query_tokens)

            top_k = min(top_k, len(jobs))

            top_indices = sorted(
                range(len(scores)),
                key = lambda i: scores[i],
                reverse=True
            )[:top_k]

            results = []

            for idx in top_indices:

                job = jobs[idx].copy()
                job["bm25_score"] = float(scores[idx])

                results.append(job)

            return results
            
        except Exception as e:
            logger.warning(f"Error in BM25 retriever: {e}")





