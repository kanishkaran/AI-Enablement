from langchain_aws import ChatBedrock
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from typing import Any, Dict
from langchain_openai import AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

import json
import time
import os
from dotenv import load_dotenv 

load_dotenv()

TASK_PROMPTS = {
    "application_development": "Write a React component for a button that changes color on click (blue to red). Use useState for color state and inline styles. The output should be only code. make sure not to exceed 300 characters",
    "automation_scripts": "Write a Python script to rename all .txt files in the current folder to add 'backup_' prefix. Handle errors and print success count. make sure not to exceed 300 characters",
    "data": "Given a users table (id, name, age), write SQL to find users over 30, sorted by age descending. The output should only be query, make sure not to exceed 300 characters"
}


def get_models(model_list: Dict[str, str]):
    """Initialise and returns models of different providers"""
    models = {}
    for model_name, model_id in model_list.items():

        if model_name == "ollama": 
            models[model_name] = ChatOllama(model=model_id)
        elif model_name == "gemini":
            models[model_name] = ChatGoogleGenerativeAI(model=model_id)
        elif model_name == "openai":
            models[model_name] = AzureChatOpenAI(
            azure_deployment="gpt-4.1",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("OPENAI_API_VERSION")
            )
        else:
            models[model_name] = ChatBedrock(model_id=model_id)
    return models


def evaluate_response(model_name: str, response: Any, prompt: str, evaluator_model: Any, latency: float):
    """Evaluates the response from the model using a separate LLM evaluator"""
    
    response_content = response.content if hasattr(response, 'content') else str(response)
    
    evaluation_prompt = f"""You are an expert AI Response evaluator. Evaluate the following model response based on the given criteria.

    Model Name: {model_name}
    Original Prompt: {prompt}
    Model Response: {response_content}
    Response Latency: {latency:.2f} seconds

    Please evaluate the response on the following criteria and provide ratings:
    1. Code Quality: Rate as "excellent", "good", "basic or limited support", or "not supported"
    2. SQL Generation: Rate as "excellent", "good", "basic or limited support", or "not supported"
    3. Infrastructure Automation (Scripts): Rate as "excellent", "good", "basic or limited support", or "not supported"
    4. Ease of Use: Rate as "excellent", "good", "basic or limited support", or "not supported"
    5. Speed/Latency: Rate as "excellent", "good", "basic or limited support", or "not supported"

    Provide your evaluation in the following JSON format:
    {{
    "code_quality": "rating",
    "sql_generation": "rating",
    "infrastructure_automation": "rating",
    "ease_of_use": "rating",
    "speed_latency": "rating",
    "comments": "Your detailed comments about the model's performance, strengths, and weaknesses"
    }}

    Only return the JSON object, no additional text.
    Make sure to be strict, fair and not to leave any edge-cases to be evaluated.
    """

    try:
        evaluation_response = evaluator_model.invoke(evaluation_prompt)
        evaluation_content = evaluation_response.content if hasattr(evaluation_response, 'content') else str(evaluation_response)
        
       
        evaluation_content = evaluation_content.strip()
        if evaluation_content.startswith("```"):
            
            lines = evaluation_content.split("\n")
            evaluation_content = "\n".join(lines[1:-1]) if lines[-1].strip().startswith("```") else "\n".join(lines[1:])
        
        evaluation_data = json.loads(evaluation_content)
        
        # Add metadata
        evaluation_data["latency_seconds"] = latency
        evaluation_data["model_name"] = model_name
        
        return evaluation_data
    except json.JSONDecodeError as e:
        # Fallback if JSON parsing fails
        return {
            "model_name": model_name,
            "code_quality": "not supported",
            "sql_generation": "not supported",
            "infrastructure_automation": "not supported",
            "ease_of_use": "not supported",
            "speed_latency": "not supported",
            "latency_seconds": latency,
            "comments": f"Error parsing evaluation JSON: {str(e)}"
        }
    except Exception as e:
        return {
            "model_name": model_name,
            "code_quality": "not supported",
            "sql_generation": "not supported",
            "infrastructure_automation": "not supported",
            "ease_of_use": "not supported",
            "speed_latency": "not supported",
            "latency_seconds": latency,
            "comments": f"Evaluation error: {str(e)}"
        }
    
def get_response_from_models(models: Dict[str, Any], prompts: Dict[str, str], evaluator_model: Any):
    """Gets the response from the models and evaluates them"""
    results = {}
    for model_name, model in models.items():
        results[model_name] = {}
        for task_name, task_prompt in prompts.items():
           
            start_time = time.time()
            response = model.invoke(task_prompt)
            latency = time.time() - start_time
            
            # Evaluate response using separate LLM
            evaluation = evaluate_response(model_name, response, task_prompt, evaluator_model, latency)
            results[model_name][task_name] = {
                "response": response.content if hasattr(response, 'content') else str(response),
                "evaluation": evaluation
            }
            print(f"{model_name} - {task_name}: {response.content if hasattr(response, 'content') else response}")
            print(f"Evaluation: {json.dumps(evaluation, indent=2)}")

    return results


MODEL_LIST = {
    "gemini": "gemini-2.5-flash",
    "ollama": "deepseek-r1:14b",
    "bedrock_claude_3_5_sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "gpt_oss": "openai.gpt-oss-safeguard-20b",
    "openai":"gpt-4.1",
}

def save_results_to_markdown(results: Dict[str, Any]) -> str:
    """Saves the results to a Markdown file"""
    markdown = "# Model Comparison Results\n\n"
    for model_name, model_results in results.items():
        markdown += f"## Model: {model_name}\n\n"
        for task_name, task_result in model_results.items():
            markdown += f"### Task: {task_name}\n\n"
            markdown += f"**Prompt:**\n{TASK_PROMPTS[task_name]}\n\n\n"
            markdown += f"**Response:**\n{task_result['response']}\n\n"
            markdown += f"**Evaluation:**\n```json\n{json.dumps(task_result['evaluation'], indent=2)}\n```\n\n"
        markdown += "---\n\n"
    return markdown

# Evaluator model for Groq
EVALUATOR_MODEL = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

def main():
    """Main function"""
    models = get_models(MODEL_LIST)
    results = get_response_from_models(models, TASK_PROMPTS, EVALUATOR_MODEL)
    
    # Save results to a Markdown file
    with open("1_model_compare/results.md", "w") as f:
        f.write(save_results_to_markdown(results))
    
    print("\nResults saved to results.md")

if __name__ == "__main__":
    main()