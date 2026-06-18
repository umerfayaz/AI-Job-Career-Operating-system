import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional
from chromadb.utils import embedding_functions
import structlog
from backend.config.settings import Settings
from datetime import datetime, timedelta
import json
import hashlib
import os


logger = structlog.get_logger()
settings = Settings()

class MemoryRAGSystem:
    """
    Persistent memory system with RAG capabilities
    """
    def __init__(self, persistent_directory: str = None, postgres_db=None):
        if persistent_directory is None:
            persistent_directory = settings.CHROMA_PATH
            os.makedirs(persistent_directory, exist_ok=True)

        logger.info(f"Initializing Memory system at {persistent_directory}")
   
        self.client = chromadb.PersistentClient(
            path=persistent_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self.postgres_db = postgres_db

        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-large-en-v1.5",
            normalize_embeddings=True
        )

        self.embedding_model = SentenceTransformer(
            "BAAI/bge-large-en-v1.5"
        )

        self._initialize_collections()

        self.job_postings_collection = self.job_collection
        self.jobs_posting_collection = self.job_collection
        self.match_history_collection = self.match_collection

        logger.info(" Memory System Initialized")

    def _initialize_collections(self):

        self.resume_collection = self._get_or_create_collection(
            name ="resumes_v2",
            description="User resume embeddings"
        )

        self.job_collection = self._get_or_create_collection(
            name="jobs_v2",
            description="Scripe Job postings BG2"
        )

        self.match_collection = self._get_or_create_collection(
            name="successful_matches_v2",
            description="Resume-job match history"
        )

        try:
            self.preferences_collection = self.client.get_collection("user_preferences")
            self.preferences_collection.count()
            logger.info("Retrieving existing  'user_preferences' collection" )
        except:
            try:
                self.client.delete_collection("user_preferences")
            except:
                pass
            self.preferences_collection = self.client.create_collection(
                name="user_preferences",
                metadata={"description": "Learned User Preferences collection"}
            )
    
    def _get_or_create_collection(self, name:str, description: str):
        try:
            collection = self.client.get_collection(
                name=name,
                embedding_function=self.embedding_function
            )
            collection.count()
            logger.info(f" Retrieved '{name}' ({collection.count()}) items")
            return collection
        
        except Exception as e:
            logger.info(f" Creating new '{name}' collection ")
            try:
                self.client.delete_collection(name)
            except:
                pass

            return self.client.create_collection(
                name=name,
                embedding_function= self.embedding_function,
                metadata={"description": description, "hnsw:space": "cosine"}
            )
    
    async def get_resume_by_id(self, user_id: str) -> Optional[str]:
        try:
            result = self.resume_collection.get(
                ids=[user_id],
                limit=1,
                include=["documents", "metadatas"]
            )

            if result and result.get("ids"):
                return result["documents"][0]
            
            logger.warning(f"No resume found for {user_id}")
            return None
        
        except Exception as e:
            logger.error(f"error in retriveing resume {e}")
            return None

    def _clean_metadata(self, data: Dict) -> Dict:
        """Clean metadata to ensure ChromaDB compatibility"""
        clean = {}
        for k, v in data.items():
            if v is None:
                clean[k] = ""
            elif isinstance(v, (str, int, float, bool)):
                clean[k] = v
            else:
                clean[k] = str(v)
        return clean

    async def store_resume(
        self,
        user_id: str,
        resume_text: str,
        skills: List[str],
        experience_years: int,
        metadata: Dict = None
    ) -> str:
        """Store resume in vector database for future reference"""

        resume_id=user_id

        base_metadata = {
            "user_id": user_id,
            "resume_id": resume_id,            
            "skills": json.dumps(skills),
            "experience_years": float(experience_years),
            "created_at": datetime.now().isoformat()
        }

        if isinstance(metadata, dict):
            base_metadata.update(metadata)

        base_metadata = self._clean_metadata(base_metadata)

        self.resume_collection.add(
            documents=[resume_text],
            metadatas=[base_metadata],
            ids=[resume_id]
        )

        if self.postgres_db:
            await self.postgres_db.save_resume_history({
                "user_id": user_id,
                "run_id": base_metadata.get("run_id"),
                "resume_version": base_metadata.get("resume_version", "v1"), 
                "summary": resume_text[:1000],
                "skills": skills,
                "experience_years": base_metadata.get("experience_years"),
                "source": "resume_upload"
            })

        logger.info(f" Stored resume {resume_id} for user {user_id}")
        return resume_id

    async def find_similar_resumes(
        self,
        resume_text: str,
        n_results: int = 5,
    ) -> List[Dict]:
        """Find similar resumes for RAG"""

        try:
            count = self.resume_collection.count()
            if count == 0:
                logger.info("Resume collection is empty")
                return []
            
            n_results = min(n_results, count)

            results = self.resume_collection.query(
                query_texts=[resume_text],
                n_results=n_results,
            )
    
            similar_resumes = []
            if results['ids'] and results['ids'][0]:
                for i, resume_id in enumerate(results['ids'][0]):
                    similar_resumes.append({
                        'resume_id': resume_id,
                        'similarity': float(1 - results['distances'][0][i]),
                        'metadata': results['metadatas'][0][i],
                        'skills': json.loads(results['metadatas'][0][i].get('skills', '[]')),
                    })

            logger.info(f"Found {len(similar_resumes)} similar resumes")
            return similar_resumes
        
        except Exception as e:
            logger.info(f"Error finding similar {e}")

            try:
                self.job_collection = self._get_or_create_collection(
                    name="jobs",
                    description="Scraped job postings"
                )
            except Exception as rienit_error:
                logger.error(f" Failed to reintialized jobs {rienit_error}")
            return []
    
    async def store_jobs(self, jobs: list[Dict], search_context: Dict = None) -> int:
        """Store scraped jobs in memory WITH MANDATORY run_id validation"""
        store_count = 0
        skipped_count = 0
        updated_count = 0
        
        if not search_context:
            logger.error("❌ CRITICAL: search_context is None!")
            raise ValueError("search_context is required for store_jobs")
        
        run_id = search_context.get('run_id')
        
        if not run_id:
            logger.error("❌ CRITICAL: store_jobs called WITHOUT run_id!")
            raise ValueError("run_id is REQUIRED in search_context")
        
        logger.info(f"📦 store_jobs called WITH run_id: {run_id}")
        logger.info(f"   Storing {len(jobs)} jobs")
        
        for job in jobs:
            try:
                title = str(job.get('job_title') or job.get('title') or "unknown").strip()
                company = str(job.get('company') or job.get('company_name') or 'unknown').strip()
                safe_location = str(job.get('location') or "").strip()
                
                url =  (job.get('url') or job.get('apply_link') or job.get('job_google_link') or "").strip()

                base_key = url.strip()
                if not base_key:
                    base_key = f"{title.lower()} | {company.lower()} | {safe_location}"
                
                job_uid = hashlib.sha256(base_key.encode("utf-8")).hexdigest()[:24]
                job_id = f"job_{job_uid}"


                if url and len(url) >10:
                    try:
                        existing_by_url =  self.job_collection.get(
                            where={"url": url},
                            limit=1,
                            include=["metadatas"]
                        )

                        if existing_by_url and existing_by_url.get("ids"):
                            existing_id = existing_by_url["ids"][0]
                            existing_meta = existing_by_url["metadatas"][0]

                            # Separating Between Apis Jsearch/ Remotive
                            existing_source = existing_meta.get("source", "")
                            incoming_source = job.get("source", "")

                            if existing_source != incoming_source:
                                self.job_collection.update(
                                    ids=[existing_id],
                                    metadatas=[self._clean_metadata({
                                        **existing_meta,
                                        "run_id": run_id,
                                        "is_fresh": True,
                                        "source": incoming_source,
                                        "updated_at": datetime.now().isoformat(),
                                    })]
                                )
                                updated_count +=1
                                continue

                            age_days = (datetime.now().timestamp() - float(existing_meta.get("created_at", 0))) / 86400

                            if age_days <1:
                                logger.debug(f"resung recent job {title}")
                                self.job_collection.update(
                                    ids=[existing_id],
                                    metadatas=[self._clean_metadata({
                                        **existing_meta,
                                        "run_id": run_id,
                                        "is_fresh": True,
                                        "reused": datetime.now().isoformat()
                                    })]
                                )
                                skipped_count +=1
                                continue
                            else:
                                logger.info(f"updating old jobs {title}")
                                self.job_collection.update(
                                    ids=[existing_id],
                                    metadatas=[self._clean_metadata({
                                        **existing_meta,
                                        "run_id": run_id,
                                        "is_fresh": True,
                                        "updated_at": datetime.now().isoformat(),
                                        "created_at": datetime.now().timestamp()
                                    })]
                                )
                                updated_count +=1
                                continue
                    
                    except Exception as e:
                        logger.debug(f"check failed: {e}")
                        pass

                job_text = f""" 
                Title: {title}
                Company: {company}
                Location: {safe_location}
                Description: {job.get('description', '')}
                """

                metadata = {
                    "job_title": job.get("job_title") or job.get("title", "unknown"),
                    "company": company,
                    "location": (
                        job.get("job_city") or
                        job.get("job_state") or
                        job.get("job_country") or
                        job.get("location") or
                        "Remote/Not Specified"
                    ),
                    "salary_range": (
                        job.get("job_salary") or
                        job.get("job_min_salary") or
                        job.get("salary") or
                        "Not Specified"
                    ),
                    "description": (job.get("description") or "")[:200],
                    "job_highlights": str(job.get("job_highlights", "")),
                    "search_key": search_context.get("search_key", ""),
                    "search_fingerprint": search_context.get("search_fingerprint", ""),
                    "job_responsibility": str(job.get("job_responsibility", "")),
                    "job_qualifications": str(job.get("job_qualifications", "")),
                    "url": (
                        job.get("url") or
                        job.get("apply_link") or
                        job.get("job_google_link") or
                        job.get("google_apply_link") 
                    ),
                    
                    "employment_type": job.get("job_employment_type") or job.get("employment_type", "full_time"),
                    "posted_date": job.get("job_posted_at_datetime_utc") or "",
                    "source": job.get("source", "jsearch_api"),
                    "run_id": run_id,
                    "is_fresh": True,
                    "created_at": datetime.now().timestamp()
                }

                metadata = self._clean_metadata(metadata)
                
                self.job_collection.add(
                    metadatas=[metadata],
                    documents=[job_text],
                    ids=[job_id]
                )

                store_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to store job {job.get('title', 'unknown')}: {e}")
                continue
        
        logger.info(f"📦 Storage complete: Stored {store_count}, Skipped {skipped_count}")
        return store_count

    async def find_similar_jobs(self, job_description: str, n_results: int = 10) -> List[Dict]:
        """Find similar jobs from past searches"""
        
        results = self.job_collection.query(
            query_texts=[job_description],
            n_results=n_results,
           
        )

        similar_jobs = []
        if results['ids'] and results['ids'][0]:
            for i, job_id in enumerate(results['ids'][0]):
                similar_jobs.append({
                    'job_id': job_id,
                    'similarity': float(1 - results['distances'][0][i]),
                    'metadata': results['metadatas'][0][i]
                })
        return similar_jobs

    async def store_successful_match(
        self, 
        user_id: str,
        resume_id: str, 
        job: Dict,
        match_score: float,
        user_action: str = "shown",
        feedback: Optional[str] = None,
        run_id: Optional[str] = None
    ):
        """Store successful matches with proper deduplication"""
        
        job_id = job.get('id', '')
        if not job_id:
            company = job.get('company', 'unknown')
            title = job.get('title') or job.get('job_title', 'unknown')
            job_location = job.get('location', 'Uknown Location')
            job_id = f"job_{run_id}_{company}_{title}".replace(' ', '_').replace('/', '_').replace('-', '_')[:200]
        
        unique_match_id = f"match_{user_id}_{job_id}"
                

        job_title = job.get('title') or job.get('job_title', 'Unknown Position')
        job_company = job.get('company', 'Unknown Company')
        job_location = job.get('location', 'Unknown Location')
        
        match_text = f"{job_title} at {job_company} in {job_location} match {match_score:.2f}"

        job_url = (
            job.get('url') or
            job.get('apply_link') or
            job.get('job_google_link') or
            job.get('google_apply_link')
        ) 

        redirect_link = f"http://localhost:8000/apply?job_id={job_id}&user_id={user_id}"
        
        metadata = {
            'user_id': user_id,
            'resume_id': resume_id,
            'job_id': job_id,
            'run_id': run_id or "",
            'is_fresh': True if run_id else False,
            'job_title': job_title,
            'company': job_company,
            'match_score': float(match_score),
            'job_location': job_location,
            'user_action': user_action,
            'url': job_url,
            'redirect_url': redirect_link,
            'feedback': feedback or '',
            'created_at': datetime.now().isoformat()
        }

        metadata = self._clean_metadata(metadata)

        try:
            existing = self.match_collection.get(ids=[unique_match_id])
            if existing and existing.get('ids'):

                self.match_collection.update(
                    ids=[unique_match_id],
                    metadatas=[metadata]
                )
                logger.info(f"Updated existing match {job_id} with new run_id={run_id}")
                return unique_match_id
        except Exception as e:
            logger.warning(f"Error checking for duplicate match: {e}")
        
        self.match_collection.add(
            documents=[match_text],
            metadatas=[metadata],
            ids=[unique_match_id]
        )
        
        logger.info(f" New match stored: {user_action} {match_score:.2f}")
        return unique_match_id
    
    async def get_job_by_id(self, job_id: str, user_id: str):
        try:
            match_id = f"match_{user_id}_{job_id}"

            result = self.match_collection.get(
                ids=[match_id],
                include=["metadatas", "documents"]
            )

            if result and result.get("ids"):
                logger.debug(f"Found job_id {job_id} by match_id")
            
                return {
                    "metadata": result["metadatas"][0],
                    "document": result["documents"][0] if result.get("documents") else ""
                }

            result = self.match_collection.get(
                where= {
                    "$and": [
                        {"job_id": {"$eq":job_id}},
                        {"user_id": {"$eq": user_id}}
                    ]
                },
                limit=1,
                include=["metadatas", "documents"]
            )

            if result and result.get("ids"):
                logger.debug(f"Found job {job_id} by metadata search")
                return {
                    "metadata": result["metadatas"][0],
                    "document": result["documents"][0] if result.get("documents") else ""
                }
            logger.warning(f" Job not found {job_id} for {user_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

    async def get_user_match_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Retrieve user's past matches for learning"""
        try:
            results = self.match_collection.get(
                where={'user_id': user_id},
                limit=limit
            )

            match_history = []
            if results['ids']:
                for i, match_id in enumerate(results['ids']):
                    match_history.append({
                        'match_id': match_id,
                        'metadata': results['metadatas'][i]
                    })

            return match_history

        except Exception as e:
            logger.warning(f"No match history found: {e}")
            return []

    async def update_user_preferences(self, user_id: str, preferences: Dict):
        """Store or update user preferences"""
        pref_id = user_id
        clean_metadata = {}

        for key, value in preferences.items():
            if isinstance(value, list):
                clean_metadata[key] = ', '.join(str(v) for v in value)
            elif isinstance(value, (str, int, float, bool)):
                clean_metadata[key] = value
            elif value is None:
                clean_metadata[key] = ""
            else:
                clean_metadata[key] = str(value)

        pref_text = json.dumps(preferences)

        try:
            existing = self.preferences_collection.get(ids=[pref_id])
            if existing['ids']:
                self.preferences_collection.update(
                    ids=[pref_id],
                    documents=[pref_text],
                    metadatas=[{
                        'user_id': user_id,
                        'updated_at': datetime.now().isoformat(),
                        **clean_metadata
                    }]
                )
                logger.info(f" Updated preferences for {user_id}")
            else:
                raise ValueError("Not found")
        except:
            self.preferences_collection.add(
                ids=[pref_id],
                documents=[pref_text],
                metadatas=[{
                    'user_id':user_id,
                    'created_at': datetime.now().isoformat(),
                    **clean_metadata
                }]
            )
            logger.info(f" Created preferences for {user_id}")

    async def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve learned user preferences"""
        pref_id = user_id
        try:
            results = self.preferences_collection.get(ids=[pref_id])
            if results['ids']:
                return results['metadatas'][0]
            else:
                return None
        except Exception as e:
            logger.warning(f"No preferences found for {user_id}: {e}")
            return None

    async def get_rag_context_for_matching(self, user_id: str, resume_text: str, run_id: str, current_jobs: List[Dict]) -> Dict:
        """Get all relevant context for intelligent matching"""
        logger.info(f"🔍 Retrieving RAG context")

        if not resume_text or not resume_text.strip():
            return {
                "similar_jobs": [],
                "similar_resumes": [],
                "match_history": [],
                "user_preferences": {},
                "similar_past_jobs": [],
                "context_quality": 0.2,
            }

        similar_resumes = await self.find_similar_resumes(resume_text, n_results=3)
        match_history = await self.get_user_match_history(user_id, limit=10)
        preferences = await self.get_user_preferences(user_id)

        similar_jobs = []
        if current_jobs:
            job_desc =next(
                (j.get('description') for j in current_jobs if j.get('description') and str(j.get('description')).strip()),
                None
            )
            if job_desc:
                similar_jobs = await self.find_similar_jobs(job_desc, n_results=5)
            else:
                logger.info("No description is available skipping skipping similar jobs lookup")

        context = {
            'similar_jobs': similar_jobs,
            'similar_resumes': similar_resumes,
            'match_history': match_history,
            'user_preferences': preferences or {},
            'similar_past_jobs': similar_jobs,
            'context_quality': await self._calculate_context_quality(
                similar_resumes, match_history, preferences
            )
        }

        logger.info(f" RAG context quality: {context['context_quality']}")
        return context

    async def mark_old_jobs_as_stale(self, hours: int = 24):
        """Mark old jobs as stale"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_timestamp = cutoff_time.timestamp()

            fresh_jobs = self.job_collection.get(
                where={"is_fresh": True},
                include=["documents", "metadatas"]
            )

            if not fresh_jobs or not fresh_jobs.get("ids"):
                logger.warning("No fresh jobs found")
                return 0
            
            stale_count = 0

            for idx, job_id in enumerate(fresh_jobs["ids"]):
                metadata = fresh_jobs["metadatas"][idx]
                created_at = metadata.get("created_at", 0)

                if float(created_at) < cutoff_timestamp:
                    try:
                        updated_metadata = metadata.copy()
                        updated_metadata["is_fresh"] = False

                        self.job_collection.update(
                            ids=[job_id],
                            metadatas=[updated_metadata]
                        )

                        stale_count += 1
                    
                    except Exception as e:
                        logger.warning(f"Failed to mark {job_id} as stale: {e}")
                        continue
            
            logger.info(f" Marked {stale_count} old jobs as stale (older than {hours}h)")
            return stale_count
        
        except Exception as e:
            logger.error(f"Error marking old jobs: {e}")
            return 0
    
    async def clean_old_jobs(self, days: int = 30):
        """Delete old jobs"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff_time.timestamp()

            all_jobs = self.job_collection.get(include=["metadatas"])
            
            old_jobs_ids = []
            for idx, job_id in enumerate(all_jobs["ids"]):
                created_at = all_jobs["metadatas"][idx].get("created_at", 0)
                if float(created_at) < cutoff_timestamp:
                    old_jobs_ids.append(job_id)
            
            if old_jobs_ids:
                self.job_collection.delete(ids=old_jobs_ids)
                logger.info(f" Deleted {len(old_jobs_ids)} jobs older than {days} days")
            
            all_matches = self.match_collection.get(include=["metadatas"])

            old_match_ids = []
            for idx, match_id in enumerate(all_matches["ids"]):
                created_at_str = all_matches["metadatas"][idx].get("created_at", "")
                try:
                    created_at = datetime.fromisoformat(created_at_str).timestamp()
                    if created_at < cutoff_timestamp:
                        old_match_ids.append(match_id)
                except:
                    continue
            
            if old_match_ids:
                self.match_collection.delete(ids=old_match_ids)
                logger.info(f"Deleted {len(old_match_ids)} matches older than {days} days")
        
        except Exception as e:
            logger.warning(f"Error cleaning old data: {e}")
            return 0
    
    async def get_fresh_jobs_from_run(self, run_id: str):
        """Get fresh jobs from a specific run_id"""
        try:
            jobs = self.job_collection.get(
                where={
                    "$and": [
                        {"run_id": run_id},
                        {"is_fresh": True}
                    ]
                },
                include=["metadatas", "documents"]
            )
            if jobs and jobs.get("ids"):
                logger.info(f" Found {len(jobs['ids'])} fresh jobs from run {run_id}")
                return jobs
            else:
                logger.warning(f"⚠️ No fresh jobs found from run {run_id}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Error fetching fresh jobs from {run_id}: {e}")
            return None

    async def _calculate_context_quality(self, similar_resumes: List, match_history: List, preferences: Optional[Dict]) -> float:
        """Calculate quality score of RAG context"""
        score = 0.0
        if similar_resumes:
            score += 0.3
        if match_history:
            score += 0.4
        if preferences:
            score += 0.3
        return float(score)

    def get_memory_stats(self) -> Dict:
        """Get statistics about stored memory"""
        return {
            'resume_count': self.resume_collection.count(),
            'jobs_count': self.job_collection.count(),
            'matches_count': self.match_collection.count(),
            'preferences_count': self.preferences_collection.count(),
            'total_memory_size': (
                self.resume_collection.count()
                + self.job_collection.count()
                + self.match_collection.count()
                + self.preferences_collection.count()
            )
        }

    def reset_memory(self, collection_name: Optional[str] = None):
        """Reset memory safely"""
        if collection_name:
            self.client.delete_collection(collection_name)
        else:
            self.client.reset()
            logger.warning("⚠️ Reset entire memory")
            self._initialize_collections()
    









