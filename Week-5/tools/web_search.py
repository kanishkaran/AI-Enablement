"""
Web Search Tool using Tavily API and LangChain
"""

from typing import Optional
from langchain_tavily.tavily_search import TavilySearch
from langchain.tools import tool

class WebSearchTool:
    """
    A web search tool that uses Tavily search API through LangChain.
    """
    
    def __init__(self, api_key: Optional[str] = None, description: str = "", max_results: int = 5,):
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
        self.search_tool.description = description
    

    

def create_web_tool(name: str="WebSearch", description: str = ""):
    
    web_search_tool = WebSearchTool(description=description)
    
    @tool
    def search(query: str) -> str:
        """
        Perform a web search using Tavily.
        
        Args:
            query: Search query string
            
        Returns:
            Search results as a formatted string
        """
        try:
            results = web_search_tool.search_tool.invoke({"query": query}) 
            return results
        except Exception as e:
            return f"Error performing search: {str(e)}"
    
    search.name = name
    return search


    

    

