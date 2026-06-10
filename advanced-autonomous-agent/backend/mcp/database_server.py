# from chromadb.utils import embedding_functions
# import json
# import uuid
# from typing import List, Dict, Any, Optional
# from pathlib import Path


# class DataMCPServer:
#     def __init__(self, db_path: str = "./chroma_db", existing_client=None):
#         self.name = "database_mcp"
#         self.db_path = Path(db_path)
#         self.db_path.mkdir(parents=True, exist_ok=True)

#         try:
#             if existing_client:
#                 self.client = existing_client
#             else:                
#                 import chromadb
#                 from chromadb.config import Settings as ChromaSettings
#                 self.client = chromadb.PersistentClient(
#                     path=str(self.db_path),
#                     settings=ChromaSettings(
#                         anonymized_telemetry=False,
#                         allow_reset=True
#                     )
#                 )
#             self.chroma_available = True
#         except ImportError:
#             self.client = None
#             self.chroma_available = False

#         self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
#             model_name="sentence-transformers/all-MiniLM-L6-v2"
#         )

#     def _get_collection(self, name: str):
#         """Centralized safe collection creation"""
#         return self.client.get_or_create_collection(
#             name=name,
#             embedding_function=self.embedding_function
#         )

#     async def store_document(
#         self,
#         collection_name: str,
#         documents: List[str],
#         metadatas: Optional[List[Dict]] = None,
#         ids: Optional[List[str]] = None
#     ) -> str:
#         if not self.chroma_available:
#             return json.dumps({"error": "ChromaDB not available"})

#         collection = self._get_collection(collection_name)

#         if ids is None:
#             ids = [f"doc_{i}" for i in range(len(documents))]

#         collection.add(documents=documents, metadatas=metadatas, ids=ids)
#         return json.dumps({"status": "success", "stored": len(documents)})

#     async def query_documents(
#         self,
#         collection_name: str,
#         query_texts: List[str],
#         n_results: int = 5
#     ) -> str:
#         if not self.chroma_available:
#             return json.dumps({"error": "ChromaDB not available"})

#         collection = self._get_collection(collection_name)
#         results = collection.query(query_texts=query_texts, n_results=n_results)
#         return json.dumps(results, indent=2)

#     async def store_insight(self, insight_data: Dict[str, Any]) -> str:
#         if not self.chroma_available:
#             return json.dumps({"error": "ChromaDB not available"})

#         collection = self._get_collection("research_insights")

#         insight_id = insight_data.get("id", f"insight_{uuid.uuid4().hex}")
#         collection.add(
#             documents=[json.dumps(insight_data)],
#             metadatas=[insight_data],
#             ids=[insight_id],
#         )

#         return json.dumps({"status": "stored", "id": insight_id})












