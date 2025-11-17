import json
import uuid
import os
from typing import List, Dict, Any, Optional
from pathlib import Path


class DataMCPServer:
    """
    Database MCP Server - Simple implementation without MCP
    Handles ChromaDB or similar vector database operations
    """
    
    def __init__(self, db_path: str = "./chroma_db"):
        self.name = "database_mcp"
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Try to initialize ChromaDB if available
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            self.chroma_available = True
        except ImportError:
            print("Warning: ChromaDB not installed. Database features will be limited.")
            self.client = None
            self.chroma_available = False

    def _clean_metadata(self, data):
        """Replace None values with safe defaults to avoid ChromaDB errors."""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if v is None:
                    continue
                cleaned_value = self._clean_metadata(v)
                if cleaned_value is None:
                    cleaned[k] = cleaned_value
            return cleaned
        elif isinstance(data, list):
            cleaned_list =[]
            for item in data:
                cleaned_item =self._clean_metadata(item)
                if cleaned_item is not None:
                    cleaned_list.append(cleaned_item)
            return cleaned_list
        else:
            return data

    
    async def store_document(self, 
                            collection_name: str, 
                            documents: List[str], 
                            metadatas: Optional[List[Dict]] = None,
                            ids: Optional[List[str]] = None) -> str:
        """Store documents in the database"""
        try:
            if not self.chroma_available:
                return json.dumps({"error": "ChromaDB not available"})
            
            collection = self.client.get_or_create_collection(name=collection_name)
            
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(documents))]
            
            if metadatas:
                metadatas = [self._clean_metadata(m) for m in metadatas]
            
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            return json.dumps({
                "status": "success",
                "stored": len(documents),
                "collection": collection_name
            })
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def query_documents(self, 
                             collection_name: str, 
                             query_texts: List[str],
                             n_results: int = 5) -> str:
        """Query documents from the database"""
        try:
            if not self.chroma_available:
                return json.dumps({"error": "ChromaDB not available"})
            
            collection = self.client.get_collection(name=collection_name)
            results = collection.query(
                query_texts=query_texts,
                n_results=n_results
            )
            
            return json.dumps({
                "status": "success",
                "results": results
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def delete_collection(self, collection_name: str) -> str:
        """Delete a collection"""
        try:
            if not self.chroma_available:
                return json.dumps({"error": "ChromaDB not available"})
            
            self.client.delete_collection(name=collection_name)
            return json.dumps({
                "status": "success",
                "message": f"Collection '{collection_name}' deleted"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def list_collections(self) -> str:
        """List all collections"""
        try:
            if not self.chroma_available:
                return json.dumps({"error": "ChromaDB not available"})
            
            collections = self.client.list_collections()
            collection_names = [col.name for col in collections]
            
            return json.dumps({
                "status": "success",
                "collections": collection_names,
                "count": len(collection_names)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def store_insight(self, insight_data: Dict[str, Any], task_id: str = None)->str:
        """Store insights and research in database"""
        try:

            if task_id:
                insight_data['task_id']= task_id
                
            if not self.chroma_available:
                insights_file = self.db_path / "insights.json"
                insights = []
                if insights_file.exists():
                    with open(insights_file, "r") as f:
                         insights =json.load(f)
                
                insights.append(insight_data)

                with open(insights_file, "w") as f:
                    json.dump(insights, f , indent=2)

                    return json.dumps({
                        "status": "Success",
                        "message": "Insight is stored in file",
                        "Location": (insights_file)
                    })

            collection = self.client.get_or_create_collection(name ="research_insights")

            ## Extract text content for embeddings
            text_content = json.dumps(insight_data)
            insight_id = insight_data.get('id', f"insight_{uuid.uuid4().hex}")
            cleaned_meta = self._clean_metadata(insight_data)


            collection.add(
                documents=[text_content],
                metadatas=[cleaned_meta],
                ids=[insight_id]
            )

            return json.dumps({
                "Status":"Success",
                "message": "Insights are stored in chromaDB",
                "id": insight_data 
            })
        
        except Exception as e:
            return json.dumps({"error", str(e)})



    async def tool_call(self, tool_name: str, **kwargs) -> str:
        """Route tool calls to appropriate methods"""
        if tool_name == "store_document":
            return await self.store_document(**kwargs)
        elif tool_name == "query_documents":
            return await self.query_documents(**kwargs)
        elif tool_name == "delete_collection":
            return await self.delete_collection(**kwargs)
        elif tool_name == "store_insight":
            return await self.store_insight(**kwargs)
        elif tool_name == "list_collections":
            return await self.list_collections()
        else:
            return json.dumps({"error": f"Unknown tool '{tool_name}'"})


if __name__ == "__main__":
    import asyncio
    
    async def test():
        server = DataMCPServer()
        result = await server.list_collections()
        print(result)
    
    asyncio.run(test())
        












