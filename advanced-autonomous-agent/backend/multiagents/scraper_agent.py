
"""Scraper Agent fetching job listings from multiple Sources"""

import asyncio
from typing import List , Dict, Any
import httpx

class ScraperAgent:
    def __init__(self, api_keys: Dict[str, Any] =None):
        self.api_keys = api_keys or {}
        self.source = ["ineed", "glassdoor"]

    async def fetch_jobs(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetches jobs from multiple sources parallel"""

        tasks = [
            self._fetch_from_source(source,  criteria)
            for source in self.sources
        ] 

        result = await asyncio.gather(*tasks, return_exceptions=True)

        # Flattes duplicate
        
        all_jobs = []
        for result in results:
            if isinstance(result, List):
                all_jobs.extend(result)
       
        return self._deduplicate_jobs(all_jobs)

    
    async def _fetch_from_source(self, source: str, criteria: Dict[str, Any])-> List[Dict[str, Any]]:
        """Fetch Jobs from speicific sources"""

        ## Integrated with Exisiting job api

        async with httpx.AsyncClient() as client:
          response =  await client.post(
            f"https://api_key/{source}/jobs",

            json={
                "keywords": criteria.get("keywords", []),
                "location": criteria.get("location"),
                "experience_level": criteria.get("experince_level"),
                "limit": criteria.get("limit", 50)
            },
            headers = {"Authorization": f"Bearer:{self.api_keys.get('source', '')}"}

        )

          if response.status_code == 200:
             return response.json().get("jobs",[])
          return []
    
    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) ->List[Dict[str, Any]]:
        """Remove Duplicate Jobs
        """
        seen = set()
        unique_jobs = []

        for job in jobs:
            jobs_id = f"{job.get('company')}_{job.get('title')}_{job.get('location')}"
            if jobs_id not in seen:
                seen.add(jobs_id)
                unique_jobs.append(job)

        return unique_jobs

        





        



