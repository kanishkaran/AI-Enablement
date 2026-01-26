from pathlib import Path
from configuration import get_chat_model, Config
from langchain.tools import tool
from typing import Optional, List
import PyPDF2
import glob

class ReadFile:
    """Read file class used to extract information for documents"""
    
    def __init__(self, path: str):
        """Initialise Path and model"""
        self.base_path = Path(path)  
        self.llm = get_chat_model()  
        
    
    def _read_text_file(self, file_path: Path) -> str:  
        """Reads text file from the defined path"""
        try:
            with open(file_path, "r") as file:
                return file.read()
        except Exception as e:
            print(f"Error reading text file: {e}")
    
    def _read_pdf_file(self, file_path: Path) -> str: 
        """Reads pdf files from the given path"""
        try:
            with open(file_path, "rb") as file:  
                pdf_reader = PyPDF2.PdfReader(file)
                content = ""
                for page in pdf_reader.pages:
                    content += page.extract_text() + "\n"
                return content
        except Exception as e:
            print(f"Error reading pdf file: {e}")
    

    def _read_file_content(self, file_path: Path) -> str: 
        """Read file content based on file type"""
        if not file_path.exists():
            return f"File not found: {file_path}"

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > Config.MAX_FILE_SIZE:
            return f"File too large: {file_size_mb:.1f}MB (max: {Config.MAX_FILE_SIZE}MB)"

        file_extension = file_path.suffix.lower()

        if file_extension == '.pdf':
            return self._read_pdf_file(file_path)
        elif file_extension in ['.txt', '.md']:
            return self._read_text_file(file_path)
        else:
            return f"Unsupported file type: {file_extension}"

    def find_relevant_documents(self, query: str, max_files: int = 5) -> List[Path]:
        """Find files that might be relevant to the query"""
        all_files = []

        for ext in Config.SUPPORTED_FILE_TYPES:
            pattern = str(self.base_path / f"**/*{ext}")
            files = glob.glob(pattern, recursive=True)
            all_files.extend([Path(f) for f in files])

        if not all_files:
            return []

        query_words = query.lower().split()
        scored_files = []

        for file_path in all_files:
            filename = file_path.name.lower()
            score = sum(1 for word in query_words if word in filename)
            scored_files.append((score, file_path))

        scored_files.sort(key=lambda x: x[0], reverse=True)
        return [file_path for _, file_path in scored_files[:max_files]]

    def _summarize_content(self, content: str, query: str) -> str:  
        """Use LLM to summarize relevant content"""
        if len(content) < 500:
            return content

        try:
            response = self.llm.invoke([
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts relevant information from documents. Focus on information that directly answers or relates to the user's query. If no relevant information is found, say so clearly."
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nDocument Content:\n{content[:4000]}...\n\nPlease extract and summarize the information most relevant to the query."
                }
            ])
            return response.content
        except Exception as e:
            return f"Error processing content: {str(e)}\n\nOriginal content (truncated):\n{content[:1000]}..."


def create_read_file_tool(base_path: str, tool_name: str = "read_file"):
    """Create a ReadFile tool for a specific base path"""

    reader = ReadFile(path=base_path)

    @tool
    def read_file(query: str, specific_file: Optional[str] = None) -> str:
        """
        Read and search internal documentation files.

        Args:
            query: The question or topic you're looking for information about
            specific_file: Optional specific filename to read (if you know the exact file)

        Returns:
            Relevant information from the documentation files
        """
        try:
            if specific_file:
                file_path = reader.base_path / specific_file
                content = reader._read_file_content(file_path)  
                if "Error" in content or "not found" in content:
                    return content
                return reader._summarize_content(content, query)  
            else:
                relevant_files = reader.find_relevant_documents(query)

                if not relevant_files:
                    return f"No relevant documentation files found for query: '{query}' in {reader.base_path}"

                results = []
                for file_path in relevant_files:
                    content = reader._read_file_content(file_path)
                    if "Error" not in content and "not found" not in content:
                        summary = reader._summarize_content(content, query)
                        results.append(f"From {file_path.name}:\n{summary}")

                if not results:
                    return f"Found {len(relevant_files)} files relevant to information: '{query}'"

                return "\n\n---\n\n".join(results)

        except Exception as e:
            return f"Error accessing documentation: {str(e)}"

    read_file.name = tool_name
    return read_file
