"""
Presidio Unified  Agent
----------------------------------
Tools:
1. MCP Tool (Google Docs / Drive) – Insurance documents
2. RAG Tool (pgVector + Ollama) – HR policies
3. Web Search Tool (Tavily) – Benchmarks, trends, regulations

LLM:
- AWS Bedrock (Claude)
"""

import os
import asyncio
from typing import List
from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from langchain.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver 
from langchain_mcp_adapters.client import MultiServerMCPClient
from src.tools.web_search.web_search_tool import WebSearchTool
from src.tools.rag_tool.PgVector_tool import PgVectorRAGTool
from src.utils.prompt_cache import PromptCache
from dotenv import load_dotenv


load_dotenv()

os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGSMITH_TRACING"] = "true"

SYSTEM_PROMPT = """You are Presidio's Internal Research Agent. Help employees find accurate, actionable information from internal and external sources.

IMPORTANT: Do not change the user given input/query at any point of time while using tool calling.
The tools' input must be the user given input

TOOLS

search_and_retrieve: Internal Google Docs (insurance policies, projects, customer feedback, marketing data) only.
search_policies: HR policies (benefits, leave, compliance, procedures)  only.
search: External information (industry benchmarks, trends, regulations, best practices)

GUIDELINES

Query Analysis: Identify intent, select appropriate tool(s), consider if benchmarking adds value

Responses: 
- Direct, well-organized answers
- Always cite sources clearly
- For analysis: compare internal vs. external data
- For policies: state clearly, note compliance considerations
- Acknowledge uncertainty when appropriate

Sensitive Topics: Provide factual policy info, recommend contacting HR/legal for specifics

Tone: Professional, helpful, clear, confident yet humble

Always prioritize accuracy, cite sources, and provide actionable insights.
"""

llm = ChatBedrockConverse(
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
)

async def load_mcp_tools() -> List[BaseTool]:
    client = MultiServerMCPClient(
        {
        "client": {
            "command": "python",
            "args": ["src/tools/mcp_tool/mcp_server.py"],
            "transport" : "stdio"
        }
        }
    )

    tools = await client.get_tools()

    if not tools:
        print("No MCP tools found")
    else:
        print(f"Loaded {len(tools)} MCP tools")

    return tools

rag = PgVectorRAGTool(
    connection_string="postgresql://postgres:postgres@localhost:5433/postgres",
    collection_name="presidio_hr_policies",
    docs_directory="Week-4/Agent-Task//hr_policies",
    model_name="nomic-embed-text",
)

rag.load_and_vectorize_documents()

tavily_tool = WebSearchTool(
    api_key=os.getenv("TAVILY_API_KEY"),
    max_results=5
)

async def setup_tools():

    mcp_tool_list = await load_mcp_tools()  # Await the async call

    tools = [
        *mcp_tool_list,        
        rag.search_policies,   # HR policies
        tavily_tool.search,    # Web search
    ]
    
    print(f"✓ Total tools loaded: {len(tools)}")
    return tools

async def main():
    tools = await setup_tools()
    
    # Create agent with loaded tools
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver()
    )
    prompt_cache = PromptCache()

    while True:
        user_input = input("🧑‍💼 Ask Presidio Agent (or 'exit'): ")
        if user_input.lower() in {"exit", "quit"}:
            break
        
        cached_response = prompt_cache.get(user_input)
        
        if cached_response:
            print("\n[Cache Hit] Retrieved from cache\n")
            response = cached_response
        else:
            print("\n[Cache Miss] Querying agent...\n")

            result = await agent.ainvoke({"messages": [{"role": "user", "content": user_input}]}, {"configurable": {"thread_id": "1"}}, )
            
            # Extract the response from the agent result
            if isinstance(result, dict) and "messages" in result:
                response = result["messages"][-1].content
            else:
                response = str(result)
            
            prompt_cache.set(user_input, response)
            
        print("\nAgent Response:\n")
        print(response)
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    print("Presidio Agent Ready\n")
    
    asyncio.run(main())