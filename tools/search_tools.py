import logging
from typing import List, Dict, Any
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Performs a live web search using DuckDuckGo to find real-time sources and facts.
    
    Args:
        query: Search query string.
        max_results: Maximum number of results to fetch (default: 5).
        
    Returns:
        List of dictionaries with title, href, and body.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return formatted
    except Exception as e:
        logger.error(f"Search tool error for query '{query}': {e}")
        return [{"title": "Search Error", "url": "", "snippet": f"Web search failed: {str(e)}"}]
