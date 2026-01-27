import hashlib
import json
from typing import List, Dict, Any

class PromptCache:
    """Simple hash-based prompt cache using hashmap."""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def _create_hash(self, prompt: str, context: List = None) -> str:
        """Create hash from prompt and optional context."""
        content = prompt
        if context:
            # Include recent context in hash
            content += json.dumps([msg.content for msg in context[-4:]], sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get(self, prompt: str, context: List = None) -> Any:
        """Get cached response if exists."""
        cache_key = self._create_hash(prompt, context)
        return self.cache.get(cache_key)
    
    def set(self, prompt: str, response: Any, context: List = None):
        """Store response in cache."""
        cache_key = self._create_hash(prompt, context)
        self.cache[cache_key] = response
        
        # Keep cache size manageable (max 100 entries)
        if len(self.cache) > 100:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
    
    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        