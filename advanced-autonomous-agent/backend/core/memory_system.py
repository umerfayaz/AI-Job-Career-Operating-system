import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import structlog
from datetime import datetime
import json
import numpy as np

logger = structlog.get_logger()


class MemoryRAGSystem:
    """
    Persistent memory system with RAG capabilities
    """
    def __init__(self, persistent_directory: str = "./chromadb"):
        """Initialize Chromadb and embedding models"""


        logger.info(f"Initializing Memory system at {persistent_directory}")

        self.client = chromadb.PersistentClient(
            path=persistent_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Initialize embedding model
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Create collections
        self._initialize_collection()

        self.job_postings_collection = self.job_collection
        self.jobs_posting_collection = self.job_collection
        self.match_history_collection = self.match_collection
        self.resume_collection = self.resume_collection


        logger.info("Memory System Initialized")

    def _initialize_collection(self):
        """Create ChromaDB collections for different types"""
        # Resume embeddings
        self.resume_collection = self.client.get_or_create_collection(
            name="resumes",
            metadata={"description": "User resume embeddings"}
        )

        # Job postings
        self.job_collection = self.client.get_or_create_collection(
            name="jobs",
            metadata={"description": "Scraped job postings"}
        )

        # Successful matches
        self.match_collection = self.client.get_or_create_collection(
            name="successful_matches",
            metadata={"description": "Jobs that were good matches"}
        )

        # User preferences
        self.preferences_collection = self.client.get_or_create_collection(
            name="user_preferences",
            metadata={"description": "Learned user preferences"}
        )

        logger.info(f"Created 4 memory collections")

    def _clean_metadata(self, data: Dict) -> Dict:
        """Clean metadata to avoid NoneType errors"""
        clean = {}
        for k, v in data.items():
            if v is None:
                clean[k] = ""
            else:
                clean[k] = v
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
        resume_id = f"resume_{user_id}_{int(datetime.now().timestamp())}"

        embeddings = [float(x) for x in self.embedding_model.encode(resume_text)]

        base_metadata = {
            "user_id": user_id,
            "skills": json.dumps(skills),
            "experience_years": float(experience_years),
            "created_at": datetime.now().isoformat()
        }

        if isinstance(metadata, dict):
            base_metadata.update(metadata)

        base_metadata = self._clean_metadata(base_metadata)

        self.resume_collection.add(
            embeddings=[embeddings],
            documents=[resume_text],
            metadatas=[base_metadata],
            ids=[resume_id]
        )

        logger.info(f"Stored resume {resume_id}")
        return resume_id

    async def find_similar_resumes(
        self,
        resume_text: str,
        n_results: int = 5,
    ) -> List[Dict]:
        """Find similar resumes for RAG"""
        embeddings = [float(x) for x in self.embedding_model.encode(resume_text)]

        results = self.resume_collection.query(
            query_embeddings=[embeddings],
            n_results=n_results,
        )

        logger.info(f"🔍 Query results keys: {list(results.keys())}")

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

    async def store_jobs(
        self,
        jobs: List[Dict],
        search_context: Dict = None
    ) -> int:
        """Store scraped jobs in memory for future reference"""
        store_count = 0
        for job in jobs:
            try:
                job_id = f"job_{job.get('company', 'unknown')}_{job.get('title', 'unknown')}_{int(datetime.now().timestamp())}"
                job_id = job_id.replace(' ', '_')[:200]

                # Create searchable text
                job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('company', '')}"

                embeddings = [float(x) for x in self.embedding_model.encode(job_text)]

                metadata = {
                    'title': job.get('title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'url': job.get('url'),
                    'source': job.get('source'),
                    'scraped_at': job.get('scraped_at', datetime.now().isoformat()),
                    'search_keywords': json.dumps(search_context.get('keywords', [])) if search_context else '[]'
                }

                metadata = self._clean_metadata(metadata)

                self.job_collection.add(
                    embeddings=[embeddings],
                    documents=[job_text],
                    metadatas=[metadata],
                    ids=[job_id]
                )

                store_count += 1

            except Exception as e:
                logger.warning(f"Failed to store job: {e}")
                continue

        logger.info(f"Stored {store_count}/{len(jobs)} jobs in summary")
        return store_count

    async def find_similar_jobs(self, job_description: str, n_results: int = 10) -> List[Dict]:
        """Find similar jobs from past searches"""
        embeddings = [float(x) for x in self.embedding_model.encode(job_description)]

        results = self.job_collection.query(
            query_embeddings=[embeddings],
            n_results=n_results
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
        self, user_id: str,
        resume_id: str, job: Dict,
        match_score: float,
        user_action: str = "shown",
        feedback: Optional[str] = None
    ):
        """Store successful matches to learn user preferences"""
        match_id = f"match_{user_id}_{int(datetime.now().timestamp())}"

        match_text = f"{job.get('title', '')} at {job.get('company', '')} match {match_score:.2f}"
        embeddings = [float(x) for x in self.embedding_model.encode(match_text)]

        metadata = {
            'user_id': user_id,
            'resume_id': resume_id,
            'job_title': job.get('title', ''),
            'company': job.get('company', ''),
            'match_score': float(match_score),
            'user_action': user_action,
            'feedback': feedback or '',
            'created_at': datetime.now().isoformat()
        }

        metadata = self._clean_metadata(metadata)

        self.match_collection.add(
            documents=[match_text],
            embeddings=[embeddings],
            metadatas=[metadata],
            ids=[match_id]
        )

        logger.info(f"Stored match {user_action} {match_score:.2f}")

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
        embeddings = [float(x) for x in self.embedding_model.encode(pref_text)]

        try:
            existing = self.preferences_collection.get(ids=[pref_id])
            if existing['ids']:
                self.preferences_collection.update(
                    ids=[pref_id],
                    embeddings=[embeddings],
                    documents=[pref_text],
                    metadatas=[{
                        'user_id': user_id,
                        'updated_at': datetime.now().isoformat(),
                        **preferences
                    }]
                )
                logger.info(f"Successfully updated preferences {user_id}")
            else:
                raise ValueError("Not found")
        except:
            self.preferences_collection.add(
                ids=[pref_id],
                embeddings=[embeddings],
                documents=[pref_text],
                metadatas=[{
                    'user_id': user_id,
                    'created_at': datetime.now().isoformat(),
                    **preferences
                }]
            )
            logger.info(f"Created preferences for {user_id}")

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
            logger.warning(f"No preferences found {user_id}: {e}")
            return None

    async def get_rag_context_for_matching(self, user_id: str, resume_text: str, current_jobs: List[Dict]) -> Dict:
        """Get all relevant context for intelligent matching"""
        logger.info(f"Retrieving RAG context")

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
            job_desc = current_jobs[0].get('description', '')
            similar_jobs = await self.find_similar_jobs(job_desc, n_results=5)

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

        logger.info(f"RAG context quality {context['context_quality']}")
        return context

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
            logger.warning("Reset entire memory")
            self._initialize_collection()


    









