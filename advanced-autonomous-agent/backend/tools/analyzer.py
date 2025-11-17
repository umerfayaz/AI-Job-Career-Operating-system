import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import re


class AnalysisTools:
    """
    Analysis Tools - Simple implementation for data analysis
    """
    
    def __init__(self):
        self.name = "analysis_tools"
    
    async def analyze_text(self, text: str) -> str:
        """Analyze text content"""
        try:
            # Basic text analysis
            word_count = len(text.split())
            char_count = len(text)
            line_count = len(text.split('\n'))
            
            # Extract URLs
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, text)
            
            # Extract emails
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, text)
            
            analysis = {
                "status": "success",
                "metrics": {
                    "word_count": word_count,
                    "character_count": char_count,
                    "line_count": line_count,
                    "url_count": len(urls),
                    "email_count": len(emails)
                },
                "urls_found": urls[:10],  # Limit to first 10
                "emails_found": emails[:10],
                "timestamp": datetime.now().isoformat()
            }
            
            return json.dumps(analysis, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis"""
        try:
            # Simple keyword-based sentiment (can be replaced with proper NLP)
            positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 
                            'fantastic', 'positive', 'happy', 'love', 'best']
            negative_words = ['bad', 'terrible', 'awful', 'horrible', 'worst', 
                            'negative', 'hate', 'poor', 'disappointing', 'fail']
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count > negative_count:
                sentiment = "positive"
                score = min(positive_count / (positive_count + negative_count + 1), 1.0)
            elif negative_count > positive_count:
                sentiment = "negative"
                score = min(negative_count / (positive_count + negative_count + 1), 1.0)
            else:
                sentiment = "neutral"
                score = 0.5
            
            result = {
                "status": "success",
                "sentiment": sentiment,
                "confidence": round(score, 2),
                "positive_indicators": positive_count,
                "negative_indicators": negative_count,
                "timestamp": datetime.now().isoformat()
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def extract_keywords(self, text: str, top_n: int = 10) -> str:
        """Extract keywords from text"""
        try:
            # Simple frequency-based keyword extraction
            # Remove common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                         'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 
                         'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had'}
            
            # Tokenize and count
            words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            word_freq = {}
            
            for word in words:
                if word not in stop_words:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Sort by frequency
            keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
            
            result = {
                "status": "success",
                "keywords": [{"word": word, "frequency": freq} for word, freq in keywords],
                "total_unique_words": len(word_freq),
                "timestamp": datetime.now().isoformat()
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def analyze_data_structure(self, data: Any) -> str:
        """Analyze data structure"""
        try:
            def get_type_info(obj):
                if isinstance(obj, dict):
                    return {
                        "type": "dict",
                        "keys": list(obj.keys())[:20],
                        "size": len(obj)
                    }
                elif isinstance(obj, list):
                    return {
                        "type": "list",
                        "length": len(obj),
                        "sample_types": list(set(type(x).__name__ for x in obj[:10]))
                    }
                else:
                    return {
                        "type": type(obj).__name__,
                        "value": str(obj)[:100]
                    }
            
            analysis = {
                "status": "success",
                "structure": get_type_info(data),
                "timestamp": datetime.now().isoformat()
            }
            
            return json.dumps(analysis, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def call_tool(self, tool_name: str, **kwargs) -> str:
        """Route tool calls to appropriate methods"""
        if tool_name == "analyze_text":
            return await self.analyze_text(**kwargs)
        elif tool_name == "analyze_sentiment":
            return await self.analyze_sentiment(**kwargs)
        elif tool_name == "extract_keywords":
            return await self.extract_keywords(**kwargs)
        elif tool_name == "analyze_data_structure":
            return await self.analyze_data_structure(**kwargs)
        else:
            return json.dumps({"error": f"Unknown tool '{tool_name}'"})


if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = AnalysisTools()
        text = "This is a great and wonderful test. Python is amazing!"
        result = await analyzer.analyze_sentiment(text)
        print(result)
    
    asyncio.run(test())