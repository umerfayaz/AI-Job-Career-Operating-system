import structlog

logger = structlog.get_logger()

class ReciprocalRank:
    
    def fuse(self, dense_results, bm25_results, top_k: int = 30):

        scores = {}
        job_lookup = {}

        for rank, job in enumerate(dense_results):
            job_id = str(job["id"])

            if job_id not in job_lookup:
                job_lookup[job_id] = job.copy()
            
            dense_score =  job.get("dense_score")
            if dense_score is not None:
                job_lookup[job_id]["dense_score"] = dense_score


            scores.setdefault(job_id, 0)
            scores[job_id] += 1 /(top_k + rank + 1)

        logger.warning(f"Dense Results: {len(dense_results)}")
        logger.warning(
            f"Dense First Score: {dense_results[0].get('dense_score') if dense_results else None}"
        )
            
        for rank, job in enumerate(bm25_results):
            job_id = str(job["id"])

            if job_id not in job_lookup:
                job_lookup[job_id] = job.copy()
            
            bm25_score = job.get("bm25_score")
            if bm25_score is not None:
                job_lookup[job_id]["bm25_score"] = bm25_score

            scores.setdefault(job_id, 0)
            scores[job_id] +=1 / (top_k + rank + 1)
        
        logger.warning(f"BM25 results: {len(bm25_results)}" )
        logger.warning(
          f"BM25 First Score: {bm25_results[0].get('bm25_score') if bm25_results else None}"
        )
        
        ranked_jobs = sorted(
            scores.items(),
            key= lambda x: x[1],
            reverse=True
        )

        results = []

        for job_id, score in ranked_jobs:
            job =  job_lookup[job_id].copy()

            job["rrf_score"] = score

            results.append(job)

        return results
 
