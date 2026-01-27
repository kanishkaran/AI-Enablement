from langgraph.graph import StateGraph, START, END
from agents import  finance_agent, it_agent
from configuration import get_chat_model
from prompts.prompts import SUPERVISOR_SYSTEM_PROMPT
from langchain_core.messages import BaseMessage, HumanMessage
from langfuse.langchain import CallbackHandler
from typing import TypedDict, List
from dotenv import load_dotenv
import os

load_dotenv()
 

os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("LANGFUSE_PUBLIC_KEY")
os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("LANGFUSE_SECRET_KEY")
os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_BASE_URL")

class AgentState(TypedDict):
    messages : List[BaseMessage]
    next_node : str


def route_to_next_agent(state: AgentState) -> str:
    classification = state.get("next_node", "").lower()

    if "it" in classification:
        return "it_support"
    elif "finance" in classification:
        return "financer"
    else:
        print("\nAI: ",state["messages"][-1].content)
        return END



def supervisor_node(state: AgentState) -> AgentState:
    """
    Invokes the supervisor model and returns the output
    """
    messages = state.get("messages", [])
    model = get_chat_model()
    
    prompt = SUPERVISOR_SYSTEM_PROMPT.format(query=messages[-1].content)

    response = model.invoke([HumanMessage(content=prompt)])
    state["next_node"] = response.content.strip().lower()
    state["messages"] = messages + [response]

    return state
    
    

def create_workflow():
    """
    Create a Multi Agent workflow using langgraph
    
    returns:
        compiled graph
    """
    
    # supervisor = supervisor_agent.create_supervisor()
    financer = finance_agent.create_finance_agent()
    it_support = it_agent.create_it_agent()
    langfuse_handler = CallbackHandler()
    
    graph_builder = StateGraph(AgentState)
    
    #Add Nodes
    graph_builder.add_node("supervisor", supervisor_node)
    graph_builder.add_node("it_support", it_support)
    graph_builder.add_node("financer", financer)
    
    #Add Edges
    graph_builder.add_edge(START, "supervisor")
    graph_builder.add_conditional_edges("supervisor", route_to_next_agent,
                                  {
                                      "it_support": "it_support",
                                      "financer": "financer",
                                      END: END
                                  })
    
    graph_builder.add_edge("it_support", END)
    graph_builder.add_edge("financer", END)
    
    return graph_builder.compile().with_config({"callbacks": [langfuse_handler]})


def run_query(compiled_workflow, user_query: str): 
    """
    Runs Query and Prints output
    """  
   
    state = {
        "messages": {"messages": [{"role": "user", "content": user_query}]},
        "next_node": ""
    }
    try:        
        result = compiled_workflow.invoke(state)        
        return result["messages"][-1].content
    except Exception as e:        
        return f"Error processing query: {str(e)}"


if __name__ == "__main__":
    
    try:
        while True:
            user_input = input("\n\n>>>>")
            
            if user_input.lower() == "quit":
                break
            
            compiled_workflow = create_workflow()
            response = run_query(compiled_workflow, user_input)
            
            print("=="*80)
            print(f"AI: {response}")
            print("=="*80)
    except Exception as e:
        print(f"Exception occured: {e}")

