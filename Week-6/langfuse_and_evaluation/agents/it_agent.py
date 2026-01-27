from langgraph.prebuilt import create_react_agent
from configuration import get_chat_model
from tools.read_file import create_read_file_tool
from tools.web_search import create_web_tool
from prompts.prompts import IT_SUPPORT_AGENT

def create_it_agent():
    """
    Creates an IT support agent 
    """
    llm = get_chat_model()
    
    read_it_docs = create_read_file_tool("Week-6/data/it", "read_it_docs")
    web_search = create_web_tool("it_web_search", "Read Latest and Relevant Information Technology Related Information from web")
    
    tools = [read_it_docs, web_search]
    
    it_agent = create_react_agent(model=llm, tools= tools, prompt=IT_SUPPORT_AGENT, name="it_agent")
    return it_agent
