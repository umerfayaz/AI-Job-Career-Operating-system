# agent/real_job_scraper.py
"""
LEAN: Real API job scraper with smart fallback
Sources: JSearch (RapidAPI), Adzuna
"""

import asyncio
import aiohttp
import os
from typing import List, Dict
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class IntelligentJobScraper:
    """Job scraper using only real APIs with smart fallback."""

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPID_API_KEY', '')
        self.adzuna_app_id = os.getenv('ADZUNA_APP_ID', '')
        self.adzuna_app_key = os.getenv('ADZUNA_APP_KEY', '')

        self.session = None
        self.rate_limits = {}  # Track rate limits

        self.source_priority = {
            'jsearch_api': 1,
            'adzuna_api': 2
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def scrape_all_sources(
        self, keywords: List[str], location: str = "Remote", max_results: int = 50
    ) -> List[Dict]:
        """Scrape using only real APIs, fallback if first fails."""

        all_jobs = []
        sources_tried = []
        sources_succeeded = []

        source_functions = [
            (1, self.scrape_jsearch, "JSearch (Indeed/LinkedIn)"),
            (2, self.scrape_adzuna, "Adzuna")
        ]

        # Sort by priority
        source_functions.sort(key=lambda x: x[0])

        for priority, func, name in source_functions:
            sources_tried.append(name)
            if self._is_rate_limited(name):
                logger.warning(f"⏱️ {name} rate limited - skipping")
                continue

            try:
                result = await asyncio.wait_for(func(keywords, location, max_results), timeout=15)
                if result:
                    all_jobs.extend(result)
                    sources_succeeded.append(name)
                    logger.info(f"✅ {name}: {len(result)} jobs")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ {name} timed out")
            except Exception as e:
                logger.warning(f"⚠️ {name} error: {str(e)[:100]}")

            # Stop if enough jobs
            if len(all_jobs) >= max_results:
                break

        # Deduplicate
        unique_jobs = self._deduplicate(all_jobs)
        logger.info(f"Sources Tried: {sources_tried}, Succeeded: {sources_succeeded}")
        logger.info(f"Total Jobs Found: {len(unique_jobs)}")
        return unique_jobs[:max_results]

    # --------- Helpers ---------

    def _is_rate_limited(self, source: str) -> bool:
        if source not in self.rate_limits:
            return False
        last_call, cooldown = self.rate_limits[source]
        return (datetime.now() - last_call) < timedelta(seconds=cooldown)

    def _set_rate_limit(self, source: str, cooldown_seconds: int = 60):
        self.rate_limits[source] = (datetime.now(), cooldown_seconds)

    def _deduplicate(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs - SIMPLE VERSION"""
        
        unique = []
        seen_keys = set()
        
        for job in jobs:
            # Get job details
            title = str(job.get('title', '')).strip().lower()
            company = str(job.get('company', '')).strip().lower()
            url = str(job.get('url', '')).strip()
            
            # Create unique identifier
            # Use URL if available (most reliable)
            if url and len(url) > 30:
                job_key = url
            # Otherwise use title + company
            elif title and company:
                job_key = f"{title}|{company}"
            else:
                # Skip jobs without identifiers
                continue
            
            # Add if not seen before
            if job_key not in seen_keys:
                seen_keys.add(job_key)
                unique.append(job)
        
        logger.info(f"   Deduplication: {len(jobs)} → {len(unique)} unique jobs")
        return unique

    def _format_job(self, raw_data: Dict, source: str, extracted: Dict) -> Dict:
        return {
            'title': extracted.get('title', 'N/A'),
            'company': extracted.get('company', 'N/A'),
            'description': extracted.get('description', ''),
            'location': extracted.get('location', 'Not specified'),
            'salary': extracted.get('salary', 'Not specified'),
            'url': extracted.get('url', ''),
            'source': source,
            'job_type': extracted.get('job_type', 'Full-time'),
            'scraped_at': datetime.now().isoformat(),
            'real_job': True
        }

    # --------- JSearch ---------
    async def scrape_jsearch(self, keywords: List[str], location: str, limit: int = 20) -> List[Dict]:
        if not self.rapidapi_key:
            return []
        jobs = []
        query = " ".join(keywords[:2])
        url = "https://jsearch.p.rapidapi.com/search"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        params = {"query": f"{query} {location}", "num_pages": "1"}

        async with self.session.get(url, headers=headers, params=params) as response:

            if response.status == 200:
                data = await response.json()
                for job in data.get('data', [])[:limit]:
                    jobs.append(self._format_job(job, 'jsearch_api', {
                        'title': job.get('job_title'),
                        'company': job.get('employer_name'),
                        'description': job.get('job_description',''),
                        'location': job.get('city') or job.get('job_state') or job.get('job_country') or location or 'Remote',
                        'salary': self._format_salary(job),
                        'url': job.get('job_apply_link'),
                        'job_type': job.get('job_employment_type')
                    }))
            elif response.status == 429:
                self._set_rate_limit('jsearch_api', 3600)
        return jobs

    # --------- Adzuna ---------
    async def scrape_adzuna(self, keywords: List[str], location: str, limit: int = 15) -> List[Dict]:
        if not self.adzuna_app_id or not self.adzuna_app_key:
            return []
        jobs = []
        query = " ".join(keywords[:2])
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
        params = {
            "app_id": self.adzuna_app_id,
            "app_key": self.adzuna_app_key,
            "results_per_page": limit,
            "what": query,
            "where": location
        }

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                for job in data.get('results', []):
                    jobs.append(self._format_job(job, 'adzuna_api', {
                        'title': job.get('title'),
                        'company': job.get('company', {}).get('display_name'),
                        'description': job.get('description','')[:1000],
                        'location': job.get('location', {}).get('display_name', location),
                        'salary': self._format_salary_adzuna(job),
                        'url': job.get('redirect_url')
                    }))
        return jobs

    def _format_salary(self, job: Dict) -> str:
        min_sal = job.get('job_min_salary')
        max_sal = job.get('job_max_salary')
        if min_sal and max_sal:
            return f"${min_sal:,.0f} - ${max_sal:,.0f}"
        elif min_sal:
            return f"${min_sal:,.0f}+"
        return "Not specified"

    def _format_salary_adzuna(self, job: Dict) -> str:
        min_sal = job.get('salary_min')
        max_sal = job.get('salary_max')
        if min_sal and max_sal:
            return f"${min_sal:,.0f} - ${max_sal:,.0f}"
        return "Not specified"
