"""
Rag tool using PgVector, Ollama and langchain
"""
import os
from typing import Dict, Any
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_postgres import PGVector
import re
import psycopg2 
from pathlib import Path


class PgVectorRAGTool:
    """Production RAG system using PostgreSQL with pgVector extension"""
    
    def __init__(
        self,
        connection_string: str = 'postgresql://postgres:postgres@localhost:5433/postgres',
        collection_name: str = "policies",
        docs_directory: str = "./hr_policies",
        model_name: str = "nomic-embed-text"
    ):
        """
        Initialize pgVector RAG Tool
        
        Args:
            connection_string: PostgreSQL connection string
                Format: postgresql://user:password@host:port/dbname
            collection_name: Name of the collection (table) for embeddings
            docs_directory: Directory containing HR policy documents
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.docs_directory = docs_directory
        self.embeddings = OllamaEmbeddings(model=model_name)
        
        # Initialize database and pgVector extension
        self._initialize_database()
        
        # Initialize vector store
        self.vectorstore = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=self.connection_string,
            use_jsonb=True,
        )
        
        print(f"pgVector RAG Tool initialized with collection: {self.collection_name}")
    
    def _initialize_database(self):
        """Initialize PostgreSQL database with pgVector extension"""
        try:
            # Parse connection string to get database name
            
            match = re.search(r'/([^/]+)$', self.connection_string)
            db_name = match.group(1) if match else 'presidio_db'
            
            try:
                # Try to connect to the target database first
                conn = psycopg2.connect(self.connection_string)
                conn.close()
                print(f"✓ Connected to existing database: {db_name}")
            except psycopg2.OperationalError:
                # Database doesn't exist, create it
                print("Error Connecting to Database")
            
            # Now connect to the target database and enable pgVector
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            # Enable pgVector extension
            cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print("pgVector extension enabled")
            
        except Exception as e:
            print(f"Database initialization note: {str(e)}")
            print("Continuing with existing database connection...")
    
    def load_and_vectorize_documents(self, force_reload: bool = False):
        """
        Load HR policy documents and create vector embeddings
        
        Args:
            force_reload: If True, reload all documents even if already indexed
        """
        # Check if documents already indexed
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            # Check if collection exists and has data
            cursor.execute("""
                SELECT COUNT(*) FROM langchain_pg_embedding 
                WHERE collection_id = (
                    SELECT uuid FROM langchain_pg_collection 
                    WHERE name = %s
                )
            """, (self.collection_name,))
            
            count = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if count and count[0] > 0 and not force_reload:
                print(f"✓ Collection already contains {count} vectors")
                return
        except Exception as e:
            print(f"Checking existing vectors: {e}")
        
        print(f"Loading documents from {self.docs_directory}...")
        
        # Create directory if it doesn't exist
        os.makedirs(self.docs_directory, exist_ok=True)
        
        # Load different document types
        documents: list[Document] = []
        
        # Load PDF files
        if len(list(Path(self.docs_directory).glob("**/*.pdf"))) > 0:
            pdf_loader = DirectoryLoader(
                self.docs_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader # type: ignore
            )
            documents.extend(pdf_loader.load())
        
        # Load text files
        if len(list(Path(self.docs_directory).glob("**/*.txt"))) > 0:
            txt_loader = DirectoryLoader(
                self.docs_directory,
                glob="**/*.txt",
                loader_cls=TextLoader
            )
            documents.extend(txt_loader.load())
        
        # Load Word documents
        if len(list(Path(self.docs_directory).glob("**/*.docx"))) > 0:
            doc_loader = DirectoryLoader(
                self.docs_directory,
                glob="**/*.docx",
                loader_cls=Docx2txtLoader
            )
            documents.extend(doc_loader.load())
        
        if not documents:
            print(f"⚠️  No documents found in {self.docs_directory}")
            print("Please add PDF, TXT, or DOCX files to the directory.")
            return
        
        print(f"✓ Loaded {len(documents)} documents")
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        splits = text_splitter.split_documents(documents)
        print(f"✓ Split into {len(splits)} chunks")
        
        # Create embeddings and store in pgVector
        print("Creating embeddings and storing in PostgreSQL with pgVector...")
        
        # Clear existing collection if force_reload
        if force_reload:
            try:
                conn = psycopg2.connect(self.connection_string)
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM langchain_pg_embedding 
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection 
                        WHERE name = %s
                    )
                """, (self.collection_name,))
                conn.commit()
                cursor.close()
                conn.close()
                print("✓ Cleared existing vectors")
            except Exception as e:
                print(f"Note on clearing: {e}")
        
        # Add documents in batches
        batch_size = 100
        for i in range(0, len(splits), batch_size):
            batch = splits[i:i + batch_size]
            self.vectorstore.add_documents(batch)
            print(f"  Processed {min(i + batch_size, len(splits))}/{len(splits)} chunks")
        
        print(f"✓ Successfully vectorized and stored {len(splits)} chunks in pgVector")
        

    def search_policies(self, query: str, k: int = 4) -> str:
        """
        This searchs Anything Related HR policies and documents for Presidio Employees.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            Formatted search results
        """
        # Perform similarity search with scores
        results = self.vectorstore.similarity_search_with_score(query, k=k) # type: ignore
        
        if not results:
            return "No relevant policies found."
        
        # Format results with relevance scores
        formatted_results: list[str] = []
        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get('source', 'Unknown') # type: ignore
            # Lower score is better in pgVector (L2 distance)
            relevance = f"{max(0, 100 - score * 10):.1f}%"
            
            formatted_results.append(
                f"Result {i} (Relevance: {relevance}):\n"
                f"Source: {source}\n"
                f"Content:\n{doc.page_content}\n"
                f"{'-' * 80}"
            )
        
        return "\n".join(formatted_results)
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM langchain_pg_embedding 
                WHERE collection_id = (
                    SELECT uuid FROM langchain_pg_collection 
                    WHERE name = %s
                )
            """, (self.collection_name,))
            
            total_vectors = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return {
                "collection_name": self.collection_name,
                "total_vectors": total_vectors[0] if total_vectors else 0,
                "embedding_dimension": 1536  
            }
        except Exception as e:
            return {"error": str(e)}


