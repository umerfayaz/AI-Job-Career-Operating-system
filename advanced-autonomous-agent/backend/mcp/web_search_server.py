# import json
# from bs4 import BeautifulSoup
# import asyncio
# import httpx
# from typing import List, Dict, Optional
# import os



# class WebSearchMCPServer:
#     """Create Search MCP Server   -----  Simple implmentation"""

#     def __init__(self):
#         self.name = "web-mcp-search"
#         self.serper_api_key = os.getenv("SERPER_API_KEY")
    
#     async def web_search(self, query: str, max_results: int = 10) ->str:
#         """Serach the Web Using Serper API KEY"""

#         url = "https://google.serper.dev/search"

#         headers ={"X-API-KEY": self.serper_api_key, "content_type": "application/json"}
#         payload = {"q": query, "count": max_results}

#         async with httpx.AsyncClient(timeout=30) as client:
#             try:
#                 response = await client.post(url, headers=headers, json=payload)
#                 data = response.json()

#                 results = [
#                     {
#                         "title": r.get("title"),
#                         "description": r.get("description"),
#                         "url": r.get("link"),
#                         "source": r.get("displayLink", "unknown"),
#                         "snippet": r.get("snippet"),
#                         "age": r.get("age", "unknown")

#                     }
#                     for r in data.get("organic",[])
#                 ]

#                 return json.dumps(results, indent =2)

#             except Exception as e:
#                 print(f"Error: {str(e)}")
    
#     async def scrape_url(self, url: str, extract_type: str = "text") ->str:
#         """Extract the content from single url"""
#         async with httpx.AsyncClient(timeout=30) as client:
#             try:
#                 response= await client.get(url)
#                 soup = BeautifulSoup(response.text, "html.parser")

#                 if extract_type == "text":
#                     for script in soup(["script", "style"]):
#                         script.decompose()
                
#                     content = soup.get_text(separator="\n", strip=True) [:10000]

#                 elif  extract_type == "structured":
#                     content = {
#                         "title": soup.title.string if soup.title else "",
#                         "headings": [h.get_text() for h in soup.find_all(["h1", "h2","h3"])],
#                         "paragraphs": [p.get_text() for p in soup.find_all("p")[:20]],
#                         "links": [a.get("href") for a in soup.find_all("a", href=True)[:50]]
#                     }

#                     content = json.dumps(content, indent=2)
                
#                 else:
#                     content = response.text[:10000]
                
#                 return content

#             except Exception as e:
#                  print(f"Error: {str(e)}") 

    
#     async def batch_scrape(self, urls: List[str], extract_type: str ="text") ->str:
#         """Scrape Mutilple URLS Concurrently"""
#         async def scrape_single( url: str) ->str:
#             try:
#                 return await self.scrape_url(url, extract_type)
#             except Exception as e:
#                 print(f"Error Scraping url {url}: {str(e)}")

#         tasks = [scrape_single(url) for url in urls]
#         results = await asyncio.gather(*tasks, return_exceptions=True)

#         output = [
#             r if not isinstance(r, Exception) else str(r)
#             for r in results
#         ]

#         return  json.dumps(output, indent=2)
    
#     async def tool_call(self, tool_name: str, **kwargs) ->str:
#         """"Route Tool calls to approporiate Method"""

#         if tool_name == "web_search":
#             return await self.web_search(**kwargs)
        
#         elif tool_name == "scrape_url":
#             return await self.scrape_url(**kwargs)
        
#         elif  tool_name == "batch_scrape":
#             return await self.batch_scrape(**kwargs)

#         else :
#             return f"Error: {tool_name}"

     








    












 




    