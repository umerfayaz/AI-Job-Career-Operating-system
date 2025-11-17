
from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformers


class RetriverAgent:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformers(model_name)
        self.resume_embedings = None

    def process_resume(self, resume_text: str) -> np.array:
        """Generate embeddings for resume"""
        self.resume_embedings = self.model_encode(resume_text, convert_to_numpy=True)
        return self.resume_embedings

    def match_jobs(self, jobs: List[Dict[str, Any]],top_k: 10 ) ->List[Dict[List]]:
        """Match Jobs using cosine similarity"""
        if self.resume_embeddings is None:
            raise ValueError("Resumen not Processed. Call Process_resume() First.")

        ## Generate Jobs emebddings

        job_description = [
            f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}"
            for job in jobs
        ]

        job_embedings = self.model.encode(job_description, convert_to_numpy=True)

        ## Calclulate Similarities

        similarity =  np.dot(job_embedings, self.resume_embedings) / (np.linalg.norm(job_embedings, axis=1) * np.linalg.norm(self.resume_embedings))

        ### Get Top Matches
        top_indices = np.argsort(similarity)[-top_k:][::-1]

        match_jobs = []
        for idx in top_indices:
            job = job[idx].copy()
            job["match_score"] = float(similarity[idx])
            job["match_percentage"] = float(similarity[idx] * 100)
            match_jobs.append(job)
        
        return match_jobs






