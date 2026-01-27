from langgraph.prebuilt import create_react_agent
from configuration import get_chat_model
from tools.read_file import create_read_file_tool
from tools.web_search import create_web_tool
from prompts.prompts import FINANCE_AGENT_PROMPT

def create_finance_agent():
    """
    Creates a finance agent
    """
    llm = get_chat_model()
    
    read_finance_docs = create_read_file_tool("Week-6/data/finance", "read_finance_docs")
    web_search = create_web_tool("finance_web_search", "Read Latest and Relevant Finance Related Information from web")
    
    tools = [read_finance_docs, web_search]
    
    finance_agent = create_react_agent(model=llm, tools= tools, prompt=FINANCE_AGENT_PROMPT, name="finance_agent")
    return finance_agent