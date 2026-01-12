import PyPDF2
import docx
import os
import chromadb
from chromadb.utils import embedding_functions
import streamlit as st
from langchain_aws import ChatBedrock


def read_txt_files(file_path: str):
    """Reads text files"""
    
    with open(file_path, "r") as f:
        return f.read()
    
def read_pdf_file(file_path: str):
    """Read pdf files"""
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text
    

def read_docx_file(file_path: str):
    """Read word file"""
    doc = docx.Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])


def read_files(file_path: str):
    """Read documents and returns the context based on type"""
    
    _, file_extension = os.path.splitext(file_path)
      
    if file_extension == '.txt':
        return read_txt_files(file_path)
    elif file_extension == '.pdf':
        return read_pdf_file(file_path)
    elif file_extension == '.docx':
        return read_docx_file(file_path)


def split_text(text: str, chunk_size: int = 500):
    """Split text into chunks while preserving sentence boundaries"""
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if not sentence.endswith('.'):
            sentence += '.'

        sentence_size = len(sentence)

        if current_size + sentence_size > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_size = sentence_size
        else:
            current_chunk.append(sentence)
            current_size += sentence_size

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks



def process_document(file_path: str):
    """Process a single document"""
    try:
        content = read_files(file_path)

        chunks = split_text(content)

        file_name = os.path.basename(file_path)
        metadatas = [{"source": file_name, "chunk": i} for i in range(len(chunks))]
        ids = [f"{file_name}_chunk_{i}" for i in range(len(chunks))]

        return ids, chunks, metadatas
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return [], [], []


def add_to_collection(collection, ids, texts, metadatas):
    """Add documents to collection in batches"""
    if not texts:
        return

    batch_size = 100
    for i in range(0, len(texts), batch_size):
        end_idx = min(i + batch_size, len(texts))
        collection.add(
            documents=texts[i:end_idx],
            metadatas=metadatas[i:end_idx],
            ids=ids[i:end_idx]
        )

def process_and_add_documents(collection, folder_path: str):
    """Process all documents in a folder and add to collection"""
    files = [os.path.join(folder_path, file) 
             for file in os.listdir(folder_path) 
             if os.path.isfile(os.path.join(folder_path, file))]

    for file_path in files:
        print(f"Processing {os.path.basename(file_path)}...")
        ids, texts, metadatas = process_document(file_path)
        add_to_collection(collection, ids, texts, metadatas)
        print(f"Added {len(texts)} chunks to collection")


def retrieve(collection, query: str, top_k: int = 2):
    """Retrieve content using semantix search"""
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    return results

def get_context(results):
    """Extract context from search results"""
    
    context = "\n\n".join(results['documents'][0])
    return context

embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path="vector_db")

collection = client.get_or_create_collection(
    name="file_collection",
    embedding_function=embedding_function
)

def get_response(llm, query: str):
    """Retrieves and gets llm response"""
    results = retrieve(collection, query)
    context = get_context(results)
    
    prompt = f"""
    You are a helpful assistant who provides response based on the query and the context given.
    
    context: {context}
    
    query: {query}
    """
    response = llm.invoke(prompt)

    return response

# Main Streamlit app
st.title("Basic RAG System")

with st.sidebar:
    if st.button("Process Documents"):
        process_and_add_documents(collection, "documents")
        st.success("Documents processed and added to collection.")

query = st.text_input("Enter your query")

llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet-20240620-v1:0")

if st.button("Retrieve"):
    if query:
        
        response = get_response(llm, query)
        result = response.content if hasattr(response, "content") else str(response)
        st.write(result)

    else:
        st.warning("Please enter a query.")