import asyncio
import structlog
from typing import  List
from datetime import datetime
from ..core.memory_system import MemoryRAGSystem


logger = structlog.get_logger()


class EventMonitor:

    def __init__(self, memory: MemoryRAGSystem):
        self.seen_resume_ids: set[str] = set()
        self.seen_job_ids: set[str] = set()
        self.seen_match_ids:  set[str] =set()
        self.memory = memory

        ## Tracking last count
        self.resume_last_count=0
        self.job_last_count =0
        self.match_last_count = 0

        self._initialize_baseline()

    def _initialize_baseline(self):

        try:
        
            resume = self.memory.resume_collection.get()
            if resume and resume.get("ids"):
                self.seen_resume_ids = set(resume["ids"])
                self.resume_last_count = len(resume["ids"])
                logger.info(f"Baseline: {self.seen_resume_ids} Existing resume")

            # Loading existing jobs
            jobs = self.memory.job_collection.get()
            if jobs and jobs.get("ids"):
                self.seen_job_ids = set(jobs["ids"])
                self.job_last_count = len(jobs["ids"])
                logger.info(f"Baseline: {len(self.seen_job_ids)}")
            

            ## Loading existing matches
            matches = self.memory.match_collection.get()
            if matches and matches.get("ids"):
                self.seen_match_ids = set(matches["ids"])
                self.match_last_count = len(matches['ids'])
                logger.info(f"Baseline: {len(self.seen_match_ids)}")
        
        except Exception as e:
            logger.error(f" Failed to initialize  baseline {e}")
    
    async def monitor_loop(self, event_queue: asyncio.Queue):
        """Starting Event Mointori"""

        logger.info("Event Monitor Started")
        logger.info("Watching for: New resumes, matches, jobs ")

        check_interval = 120

        while True:
            try:
                new_resumes = await self._check_new_resumes()
                if new_resumes:
                    for resume_data in new_resumes:
                        await event_queue.put({
                            "type": "new_resume_uploaded",
                            "data": resume_data,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"NEW RESUME DATA DETECTED: {resume_data['resume_id']}")
                        logger.info(f" Keywords: {resume_data.get('keywords', [])}")
            

                #  checking New jobs
                new_jobs =  await self._check_new_jobs()
                
                # Check for new Matches
                new_matches = await self._check_new_matches()
                if new_matches > 0:
                    await event_queue.put({
                        "type": "new_matches",
                        "data": {"match_count": new_matches},
                        "timestamp": datetime.now().isoformat()
                    })

                    logger.info(f" NEW MATCHES DETECTED: {new_matches}")
                
                # Periodic table for checking every resume

                await self._check_periodic_stats(event_queue)


                # Sleep before next loop

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f" Event monitor error {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _check_new_resumes(self) ->list:
        """Checking if new resume is uploaded from langgraph workflow"""

        try:
            resumes = self.memory.resume_collection.get()

            if not resumes or not resumes.get("ids"):
                return []
            
            current_ids = set(resumes["ids"])
            new_ids = current_ids - self.seen_resume_ids

            if not new_ids:
                return []
            

            new_resume_data = []

            for idx, resume_id in enumerate(resumes["ids"]):
                if resume_id in new_ids:
                    metadata = resumes["metadatas"][idx] if resumes.get("metadatas") else {}


                    keywords = []

                    # Tring to get keywords from metadata
                    if "keywords" in metadata:
                        kw = metadata["keywords"]
                        if isinstance(kw, str):
                            keywords = [k.strip() for  k in kw.split(",")]
                        elif isinstance(kw, list):
                            keywords = kw
                    
                    # if no keywords trying to get from preferences
                    if not keywords:
                        user_id =  metadata.get("user_id", "")
                        if user_id:
                            try:
                                prefs = self.memory.preference_collection.get(
                                    where= {"user_id": user_id}
                                )

                                if prefs and prefs.get("metadata"):
                                    pref_kw = prefs["metadatas"][0].get("job_keywords", "")
                                    if pref_kw:
                                        if isinstance(pref_kw, str):
                                            keywords= [k.strip() for k in pref_kw.split(",")]
                                        elif isinstance(pref_kw, list):
                                            keywords = pref_kw
                            except:
                                pass

                    # if still not able to find keywords
                    if not keywords:
                        resume_text = resumes["documents"][idx] if resumes.get("documents") else ""
                        keywords = self.extract_keywords_from_text(resume_text)

                    real_user_id = (
                        metadata.get("actual_user_id") or
                        metadata.get("user_id") or
                        metadata.get("uploaded_by")
                    )

                    # If still no user_id, try preferences lookup
                    if not real_user_id:
                        try:
                            prefs = self.memory.preferences_collection.get(
                                where={"resume_id": resume_id}
                            )
                            if prefs and prefs.get("metadatas"):
                                real_user_id = prefs["metadatas"][0].get("user_id")
                        except:
                            real_user_id = None

                    new_resume_data.append({
                        "resume_id": resume_id,
                        "user_id": real_user_id,
                        "keywords": keywords[:10],
                        "metadata": metadata
                    })


                    self.seen_resume_ids.add(resume_id)
        
            return new_resume_data
        
        except Exception as e:
            logger.error(f"Error Checking new resume {e}")
            return []
    
    @staticmethod
    def extract_keywords_from_text(text: str) -> list[str]:
        if not text:
            return [
                "software engineer",
                "agentic ai engineer",
                "web developer"
            ]

        tech_keywords = [
            "python", "javascript", "react", "node", "aws", "docker",
            "kubernetes", "machine learning", "data science",
            "frontend", "backend", "full stack", "devops", "cloud",
            "api", "ai", "agentic ai", "automation engineer", "machine learning",
            "rag", "multimodal rag", "mcp",
            "langgraph", "langchain", "huggingface",
            "ai agents", "automation", "crewai", "ai engineer",
            "ai developer", "prompt engineer", "generative ai engineer",
            "generative ai", "crew ai", "autonomous agents", "python ai development"
        ]

        text_lower = text.lower()
        found = []

        for kw in tech_keywords:
            if kw in text_lower:
                found.append(kw)
                if len(found) >= 6:
                    break

        return found or [
            "software engineer",
            "agentic ai engineer",
            "web developer"
        ]

    
    async def _check_new_jobs(self) -> int:
        try:
            jobs= self.memory.job_collection.get()

            if not jobs or not jobs.get("ids"):
                return 0
            
            current_count = len(jobs["ids"])
            new_count = current_count - self.job_last_count

            if new_count > 0:

                current_ids = set(jobs["ids"])
                new_ids =   current_ids - self.seen_job_ids
                self.seen_job_ids.update(new_ids)
                self.job_last_count = current_count

                logger.info(f" New ids detected{len(new_ids)}")

                return len(new_ids)
            
            return 0
        
        except Exception as e:
            logger.error(f"error getting new jobs {e}")
            return 0
    
    async def _check_new_matches(self) -> int:

        try:
            matches = self.memory.match_collection.get()

            if not matches or not matches.get("ids"):
                return 0
            
            current_count = len(matches["ids"])
            new_count = current_count - self.match_last_count

            if new_count >0:

                current_ids = set(matches["ids"])
                new_ids = current_ids - self.seen_match_ids
                self.seen_match_ids.update(new_ids)
                self.match_last_count = current_count

                return len(new_ids)
            
            return 0
        
        except Exception  as e:
            logger.error(f" Error  checking new matches {e}")
            return 0
    
    async def _check_periodic_stats(self, event_queue: asyncio.Queue):
        """Periodic check for agents to look for their work"""
        try:
            resumes = self.memory.resume_collection.get()
            has_resumes = resumes and len(resumes.get("ids", [])) > 0

            if not has_resumes:
                logger.debug("No resumes - skipping periodic checks")
                return 

            # Get jobs and matches counts
            jobs = self.memory.job_collection.get()
            job_count = len(jobs.get("ids", [])) if jobs else 0
            
            matches = self.memory.match_collection.get()
            match_count = len(matches.get("ids", [])) if matches else 0
            
            # Only trigger if there's actual work needed
            
            # 1. JobScraper: Only if we have few jobs
            if job_count < 10:
                logger.debug("Triggering periodic: JobScraperAgent")
                await event_queue.put({
                    "type": "periodic_check",
                    "agent": "JobScraperAgent",
                    "timestamp": datetime.now().isoformat()
                })

            # ReportGeneratorAgent
            if match_count > 0:
                await event_queue.put({
                    "type": "new_matches",
                    "agent": "ReportGeneratorAgent",
                    "timestamp": datetime.now().isoformat()
                })

            # 2. MemoryMaintenance
            logger.debug(f"Triggering Periodic: MemoryMaintenanceAgent")
            await event_queue.put({
                "type": "periodic_check",
                "agent": "MemoryMaintenance",
                "timestamp": datetime.now().isoformat()
            })   
        
        except Exception as e:
            logger.error(f"Error in periodic task check: {e}")
            
    async def event_loop(self):
        while True:
            await self._check_periodic_stats()
            await asyncio.sleep(500)

            

            





    

    








             


        












    

        



