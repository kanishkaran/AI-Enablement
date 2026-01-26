"""
Web Search Tool using Tavily API and LangChain
"""

from typing import Optional
from langchain_tavily.tavily_search import TavilySearch

class WebSearchTool:
    """
    A web search tool that uses Tavily search API through LangChain.
    """
    
    def __init__(self, api_key: Optional[str] = None, max_results: int = 5):
        """
        Initialize the WebSearchTool.
        
        Args:
            api_key: Tavily API key. If not provided, will use TAVILY_API_KEY env var
            max_results: Maximum number of search results to return
        """
        self.max_results = max_results
        self.search_tool = TavilySearch(
            max_results=max_results,
            api_key=api_key
        )
        self.search_tool.description = (
        """Web search tool for retrieving current and latest publicly available information from the internet. 
        Use this when user asks about: current year, latest, recent, or 2025/2026 data. 
        Best for: industry salary benchmarks, current labor law regulations, recent compliance standards, 
        latest HR best practices, current employee benefits trends, and recent competitive compensation analysis. 
        Interprets 'current' and 'latest' as the most recent information available (typically up to current date). 
        For questions mentioning current year or 'latest', this tool will search for the most recent data available. 
        Note: Cannot predict actual future data beyond what is currently published."""
    )
    
 
    def search(self, query: str) -> str:
        """
        Perform a web search using Tavily.
        
        Args:
            query: Search query string
            
        Returns:
            Search results as a formatted string
        """
        try:
            results = self.search_tool.invoke({"query": query}) 
            return results
        except Exception as e:
            return f"Error performing search: {str(e)}"

    

