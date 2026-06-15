
"""
LEAN: Real API job scraper with smart fallback
Sources: JSearch (RapidAPI), Adzuna
"""

import asyncio
import aiohttp
import os
import time
from typing import List, Dict
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.core.event_bus import get_event_bus
from backend.narration.emitter import AgentEmitter
from backend.core.event_bus import get_event_bus
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()
event_bus = get_event_bus()

class IntelligentJobScraper:
    """Job scraper using only real APIs with smart fallback."""

    def __init__(self, shared_context, event_bus):
        self.rapidapi_key = os.getenv('RAPID_API_KEY', '')
     
        self.event_bus = event_bus
        self.emitter = AgentEmitter("JobScraperAgent", self.event_bus)
        self.shared_context = shared_context

        self.session = None
        self.rate_limits = {}  # Track rate limits

        self.source_priority = {
            'jsearch_api': 1,
            'remotive_api': 2
        }

    async def __aenter__(self):
        import socket
        connector = aiohttp.TCPConnector(family=socket.AF_INET, force_close=True)
        self.session = aiohttp.ClientSession( connector=connector,timeout=aiohttp.ClientTimeout(total=20))
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def scrape_all_sources(
        self, keywords: List[str],run_id: str, location: str = "Remote", max_results: int = 100, preferred_source="JSearch",
    ) -> List[Dict]:
        """Scrape using only real APIs, fallback if first fails."""
        with tracer.start_as_current_span("JobScraper.scrape_all_sources") as parent_span:

            try:
                parent_span.set_attribute("keywords.count", len(keywords))
                parent_span.set_attribute("scraper.location", location)
                parent_span.set_attribute("preferred_source", preferred_source)


                all_jobs = []
                sources_tried = []
                sources_succeeded = []

                if preferred_source == "Remotive":
                    source_functions = [
                        (1, self.scrape_remotive, "Remotive"),
                        # (2,  self.scrape_jsearch, "JSearch (Indeed/Linkedin)")
                    ]
                    logger.warning("Remotive Calling in Intelligent Scraper")
                
                elif preferred_source == "JSearch":
                    source_functions = [
                        (1, self.scrape_jsearch, "JSearch (Indeed/LinkedIn)"),
                        # (2, self.scrape_remotive, "Remotive")
                    ]
                    logger.warning("JSearch API Calling inside intelligent Scraper")
                
                else:
                    source_functions = [
                        (1, self.scrape_jsearch, "JSearch (Indeed/Linkedin)"),
                        # (2, self.scrape_remotive, "Remotive")
                    ]
                    logger.warning("Jsearch API Calling inside intelligent Scraper")

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
                        await self.emitter.error(
                                run_id,
                                f"No jobs available right now on {name} for {keywords} and {location}"
                            )
                        await asyncio.sleep(3.0)

                        await self.event_bus.emit({
                            "type": "API_ERROR",
                            "payload": {
                                "run_id": run_id,
                                "keywords": keywords,
                                "location": location,
                                "source": "brain1",
                                "message": f"{name} Job search Api failed timedout"
                            },
                            "timestamp": datetime.now().isoformat()                   
                        })


                    except Exception as e:
                        logger.warning(f"⚠️ {name} error: {str(e)[:100]}")
                    # Stop if enough jobs
                    if len(all_jobs) >= max_results:
                        break

                # Deduplicate
                unique_jobs = self._deduplicate(all_jobs)
                logger.info(f"Sources Tried: {sources_tried}, Succeeded: {sources_succeeded}")
                logger.info(f"Total Jobs Found: {len(unique_jobs)}")


                parent_span.set_attribute("scraper_engine.run_id", run_id)
                parent_span.set_attribute("scraper_enginer", max_results)
                parent_span.set_attribute("scraper_engine.output_jobs", len(unique_jobs))
                parent_span.set_attribute("scraper_engine.sources_tried", ",".join (sources_tried))
                parent_span.set_attribute("scrape_enginer.sources_succeeded", ",".join(sources_succeeded))
                return unique_jobs[:max_results]
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return []

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
            
        
            if url and len(url) > 30:
                job_key = url
       
            elif title and company:
                job_key = f"{title}|{company}"
            else:
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

    # JSearch 
    async def scrape_jsearch(self, keywords: List[str], location: str, limit: int = 20) -> List[Dict]:
            
        with tracer.start_as_current_span("API.JSearch") as api_span:
            start_jsearch_api = time.time()

            try:


                if not self.rapidapi_key:
                    api_span.set_attribute("JSEARCH.skipped", True )
                    api_span.set_attribute("JSEARCH.reason", "missing_key")
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
                    
                    api_span.set_attribute("api.jobs_returned", len(jobs))
                    api_span.set_attribute("http.status_code", response.status)
                    api_span.set_attribute("api.source", "Jsearch")
                    return jobs
            
            except Exception as e:
                logger.error(f"JSearch Api error: {str(e)}")
                api_span.record_exception(e)
                api_span.set_attribute("error", True)
                return jobs
            finally:
                api_span.set_attribute("JSEARCH.latency_seconds", time.time() - start_jsearch_api)

    # --------- Remotive ---------
    async def scrape_remotive(self, keywords: List[str], location: str, limit: int = 15) -> List[Dict]:
        with tracer.start_as_current_span("API.Remotive") as api_span:
            start_remotive_api = time.time()

            jobs = []
            queries = keywords[:3]
            url = f"https://remotive.com/api/remote-jobs"

            try:
                for q in queries:
                    params = {
                        "search": q
                    }
                    async with self.session.get(url, params=params) as response:
                        logger.warning("Remotive Api Function Called")

                        if response.status == 200:
                            data = await response.json()
                            job_list = data.get("jobs", [])

                            logger.warning(f" Remotive Jobs List : {len(job_list)}")
                            logger.warning(f"Remotive Sample Jobs {job_list[0].get('job_title') if job_list else 'No Jobs'}")

                            for job in job_list[:limit]:
                                jobs.append(self._format_job(job, 'remotive_api', {
                                    'title': job.get('job_title') or job.get('title'),
                                    'company': job.get('company_name') or job.get('employer_name') or 'unknown',
                                    'description': job.get('job_description','')[:3000],
                                    'location': job.get('candidate_required_location') or 'Remote',
                                    'salary': job.get('salary') or self._format_salary(job),
                                    'url': job.get('url')
                                }))    
                        else:
                            logger.error(f"Remotive API Failed: {response.status}")
                        
                        api_span.set_attribute("api.jobs_returned", len(jobs))
                        api_span.set_attribute("http.status_code", response.status )
                        api_span.set_attribute("api.source", "Remotive")
                        return jobs

            except Exception as e:
                logger.error(f"Remotive API Error: {str(e)}")
                api_span.record_exception(e)
                api_span.set_attribute("error", True)   
                return jobs
            finally:
                api_span.set_attribute("REMOTIVE.latency_seconds", time.time() - start_remotive_api) 

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
