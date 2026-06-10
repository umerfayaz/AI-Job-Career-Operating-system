
import structlog
logger = structlog.get_logger()


class JobReranker:
    def __init__(self, model):
        self.model = model

    def reranker(self, resume_text: str, jobs: list, top_k: int = 20):

        pairs = []
        for job in jobs:

            skills = ", ".join(job.get("skills", []))

            texts = f"""
            Title: {job.get("title", "")}
            Skills: {skills}
            Company: {job.get("company", "")}
            Location: {job.get("location", "")}
            Experience: {job.get("experience", "")}
            Description: {job.get("description", "")[:500]}
            """
            pairs.append(
                (
                    resume_text,
                    texts
                )
            )
        
        logger.warning(f"Reranking: {len(pairs)} jobs")

        scores = self.model.predict(pairs)

        for job, score in zip(jobs, scores):
            job["rerank_score"] = float(score)

        ranked = sorted(
            jobs,
            key= lambda x: x["rerank_score"],
            reverse=True
        )

        logger.warning(f"Top reranking {ranked[0]['rerank_score'] if ranked else None}")

        return ranked[:top_k]



