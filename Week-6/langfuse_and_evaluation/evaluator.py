from agentevals.trajectory.llm import create_trajectory_llm_as_judge, TRAJECTORY_ACCURACY_PROMPT
from workflow import create_workflow
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
import os
import time
import json
from datetime import datetime
from typing import Dict, Any, List

os.environ["AWS_REGION"] = "us-east-1"

# Custom prompts for LLM-as-judge evaluation

CORRECTNESS_JUDGE_PROMPT = """You are an expert evaluator assessing the correctness of an AI agent's response.

Task: Evaluate how correct, accurate, and appropriate the agent's response is to the given question.

Question: {question}
Agent's Response: {response}

Evaluation Criteria:
1. Factual Accuracy: Is the information provided correct and truthful?
2. Completeness: Does the response adequately address all aspects of the question?
3. Relevance: Is the response directly related to what was asked?
4. Coherence: Is the response logical and well-structured?

Provide your evaluation in the following JSON format:
{{
    "score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation of your score>",
    "strengths": "<what the response does well>",
    "weaknesses": "<what could be improved>"
}}

Score Guidelines:
- 0.9-1.0: Excellent - Highly accurate, complete, and relevant
- 0.7-0.9: Good - Mostly accurate with minor issues
- 0.5-0.7: Fair - Some accuracy issues or incompleteness
- 0.3-0.5: Poor - Significant accuracy problems
- 0.0-0.3: Very Poor - Mostly incorrect or irrelevant

Respond ONLY with the JSON object, no additional text.
"""

HALLUCINATION_JUDGE_PROMPT = """You are an expert evaluator detecting hallucinations and false information in AI agent responses.

Task: Identify if the agent's response contains any fabricated, false, or unverifiable information.

Question: {question}
Agent's Response: {response}

Evaluation Criteria:
1. Factual Verification: Can the claims be verified as true?
2. Appropriate Uncertainty: Does the agent acknowledge when it doesn't know?
3. Source Attribution: Are claims properly contextualized?
4. Logical Consistency: Are statements internally consistent?

Types of Hallucinations to Detect:
- Fabricated facts or statistics
- False claims about events, dates, or people
- Invented sources or references
- Contradictory statements
- Overconfident assertions without basis

Provide your evaluation in the following JSON format:
{{
    "hallucination_detected": <true or false>,
    "hallucination_rate": <float between 0.0 and 1.0>,
    "severity": "<none|low|medium|high>",
    "examples": ["<specific hallucination 1>", "<specific hallucination 2>"],
    "reasoning": "<explanation of your assessment>"
}}

Hallucination Rate Guidelines:
- 0.0: No hallucinations detected
- 0.1-0.2: Minor hallucinations (slight inaccuracies)
- 0.2-0.4: Moderate hallucinations (some false claims)
- 0.4-0.7: Significant hallucinations (many false claims)
- 0.7-1.0: Severe hallucinations (mostly fabricated)

Respond ONLY with the JSON object, no additional text.
"""

TOOL_USAGE_JUDGE_PROMPT = """You are an expert evaluator assessing how effectively an AI agent uses its available tools.

Task: Evaluate the agent's tool usage effectiveness.

Question: {question}
Agent's Tool Calls: {tool_calls}
Agent's Final Response: {response}

Evaluation Criteria:
1. Tool Selection: Did the agent choose appropriate tools?
2. Tool Execution: Were tools called correctly with proper parameters?
3. Result Integration: Were tool results properly used in the response?
4. Efficiency: Were unnecessary tool calls avoided?

Provide your evaluation in the following JSON format:
{{
    "score": <float between 0.0 and 1.0>,
    "tools_used": <number of tools used>,
    "tools_successful": <number of successful tool calls>,
    "efficiency": "<efficient|acceptable|inefficient>",
    "reasoning": "<explanation of your assessment>"
}}

Score Guidelines:
- 0.9-1.0: Excellent - Perfect tool selection and usage
- 0.7-0.9: Good - Appropriate tools used effectively
- 0.5-0.7: Fair - Some tool usage issues
- 0.3-0.5: Poor - Significant tool usage problems
- 0.0-0.3: Very Poor - Failed to use tools properly

Respond ONLY with the JSON object, no additional text.
"""


class LLMJudgeEvaluator:
    """Evaluator using LLM-as-judge for multiple metrics"""
    
    def __init__(self, judge_model: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"):
        """
        Initialize evaluators
        
        Args:
            judge_model: Model to use as judge
        """
        self.judge_model = judge_model
        self.workflow = create_workflow()
        self.llm = ChatBedrock(model_id=judge_model)
        
        self.trajectory_evaluator = create_trajectory_llm_as_judge(
        prompt=TRAJECTORY_ACCURACY_PROMPT,
        model=f"bedrock:{judge_model}",
    )
    
    def evaluate_single_query(self, question: str) -> Dict[str, Any]:
        """
        Evaluate agent performance on a single query
        
        Args:
            question: Query to evaluate
            
        Returns:
            Dictionary containing all evaluation results
        """
        print(f"\n{'='*60}")
        print(f"Evaluating: {question}")
        print(f"{'='*60}")
        
        # Run agent
        state = {
            "messages": [HumanMessage(content=question)],
            "next_node": ""
        }
        
        start_time = time.time()
        try:
            response = self.workflow.invoke(state)
            latency = time.time() - start_time
            
            # Extract response text and tool calls
            response_text = self._extract_response_text(response)
            tool_calls = self._extract_tool_calls(response)
            
            print(f"\n✓ Agent completed in {latency:.2f}s")
            print(f"  Response length: {len(response_text)} chars")
            print(f"  Tool calls: {len(tool_calls)}")
            
            # Evaluate with LLM judges
            print("\n Running LLM-as-Judge evaluations...")
            
            print("  → Evaluating trajectory accuracy...")
            trajectory_result = self._evaluate_trajectory_accuracy(response)
            
            
            print("  → Evaluating correctness...")
            correctness_result = self._evaluate_correctness(question, response_text)
            
            
            print("  → Detecting hallucinations...")
            hallucination_result = self._evaluate_hallucination(question, response_text)
            
            
            print("  → Evaluating tool usage...")
            tool_usage_result = self._evaluate_tool_usage(question, tool_calls, response_text)
            
            # Combine results
            evaluation = {
                "question": question,
                "response_text": response_text,
                "latency": latency,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                
                "trajectory_score": trajectory_result.get("trajectory_score", 0.0),
                "trajectory_reasoning": trajectory_result.get("trajectory_reasoning", ""),
                "trajectory_details": trajectory_result.get("trajectory_details", {}),
                
                # Correctness metrics
                "correctness_score": correctness_result.get("score", 0.0),
                "correctness_reasoning": correctness_result.get("reasoning", ""),
                "correctness_strengths": correctness_result.get("strengths", ""),
                "correctness_weaknesses": correctness_result.get("weaknesses", ""),
                
                # Hallucination metrics
                "hallucination_detected": hallucination_result.get("hallucination_detected", False),
                "hallucination_rate": hallucination_result.get("hallucination_rate", 0.0),
                "hallucination_severity": hallucination_result.get("severity", "none"),
                "hallucination_examples": hallucination_result.get("examples", []),
                "hallucination_reasoning": hallucination_result.get("reasoning", ""),
                
                # Tool usage metrics
                "tool_usage_score": tool_usage_result.get("score", 0.0),
                "tools_used": tool_usage_result.get("tools_used", 0),
                "tools_successful": tool_usage_result.get("tools_successful", 0),
                "tool_efficiency": tool_usage_result.get("efficiency", "unknown"),
                "tool_usage_reasoning": tool_usage_result.get("reasoning", ""),
                
                # Raw data
                "raw_response": response,
                "tool_calls": tool_calls
            }
            
            self._print_evaluation_summary(evaluation)
            
            return evaluation
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                "question": question,
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }
    
    def _extract_response_text(self, response: Any) -> str:
        """Extract text from agent response"""
        try:
            if isinstance(response, dict):
                if "messages" in response:
                    messages = response["messages"]
                    if messages and len(messages) > 0:
                        last_message = messages[-1]
                        if hasattr(last_message, "content"):
                            return str(last_message.content)
                        return str(last_message)
                return str(response)
            return str(response)
        except Exception:
            return "Error extracting response text"
    
    def _extract_tool_calls(self, response: Any) -> List[Dict[Any, Any]]:
        """Extract tool calls from agent response"""
        tool_calls = []
        try:
            if isinstance(response, dict) and "messages" in response:
                for msg in response["messages"]:
                    if hasattr(msg, "tool_calls"):
                        for tool_call in msg.tool_calls:
                            tool_calls.append({
                                "name": tool_call.get("name", "unknown"),
                                "args": tool_call.get("args", {})
                            })
        except Exception:
            pass
        return tool_calls
    
    def _extract_json_from_content(self, content: str) -> str:
        """Extract JSON from content, removing markdown code blocks if present"""
        content = content.strip()
        
        
        if content.startswith('```'):
            
            parts = content.split('```')
            if len(parts) >= 2:
                content = parts[1]
                
                if content.strip().startswith('json'):
                    content = content.strip()[4:]
        
        return content.strip()
    
    def _evaluate_trajectory_accuracy(self, response: Any) -> Dict[str, Any]:
        """Use trajectory evaluator to assess agent's reasoning path"""
        try:
            
            # Run trajectory evaluation
            evaluation_result = self.trajectory_evaluator(outputs=response)
            
            # Extract score and reasoning
            if isinstance(evaluation_result, dict):
                return {
                    "trajectory_score": evaluation_result.get("score", 0.0),
                    "trajectory_reasoning": evaluation_result.get("reasoning", ""),
                    "trajectory_details": evaluation_result
                }
            else:
                return {
                    "trajectory_score": 0.0,
                    "trajectory_reasoning": str(evaluation_result),
                    "trajectory_details": {}
                }
            
        except Exception as e:
            print(f"    ⚠ Error in trajectory accuracy evaluation: {e}")

    def _evaluate_correctness(self, question: str, response: str) -> Dict[str, Any]:
        """Use LLM judge to evaluate correctness"""
        try:
            prompt = CORRECTNESS_JUDGE_PROMPT.format(
                question=question,
                response=response
            )
            
            result = self.llm.invoke(prompt)
            
            # Extract content from AIMessage
            content = result.content if hasattr(result, 'content') else str(result)
            
            # Clean and parse JSON
            content = self._extract_json_from_content(content)
            return json.loads(content)
            
        except Exception as e:
            print(f"    ⚠ Error in correctness evaluation: {e}")
            return {
                "score": 0.0,
                "reasoning": f"Error: {str(e)}",
                "strengths": "N/A",
                "weaknesses": "N/A"
            }
    
    def _evaluate_hallucination(self, question: str, response: str) -> Dict[str, Any]:
        """Use LLM judge to detect hallucinations"""
        try:
            prompt = HALLUCINATION_JUDGE_PROMPT.format(
                question=question,
                response=response
            )
            
            result = self.llm.invoke(prompt)
            
            # Extract content from AIMessage
            content = result.content if hasattr(result, 'content') else str(result)
            
            # Clean and parse JSON
            content = self._extract_json_from_content(content)
            return json.loads(content)
            
        except Exception as e:
            print(f"    ⚠ Error in hallucination detection: {e}")
            return {
                "hallucination_detected": False,
                "hallucination_rate": 0.0,
                "severity": "none",
                "examples": [],
                "reasoning": f"Error: {str(e)}"
            }
    
    def _evaluate_tool_usage(self, question: str, tool_calls: List[Dict], response: str) -> Dict[str, Any]:
        """Use LLM judge to evaluate tool usage"""
        try:
            prompt = TOOL_USAGE_JUDGE_PROMPT.format(
                question=question,
                tool_calls=json.dumps(tool_calls, indent=2),
                response=response
            )
            
            result = self.llm.invoke(prompt)
            
            # Extract content from AIMessage
            content = result.content if hasattr(result, 'content') else str(result)
            
            # Clean and parse JSON
            content = self._extract_json_from_content(content)
            return json.loads(content)
            
        except Exception as e:
            print(f"    ⚠ Error in tool usage evaluation: {e}")
            return {
                "score": 0.0,
                "tools_used": len(tool_calls),
                "tools_successful": 0,
                "efficiency": "unknown",
                "reasoning": f"Error: {str(e)}"
            }
    
    def _print_evaluation_summary(self, evaluation: Dict[str, Any]):
        """Print a summary of evaluation results"""
        print("\nEvaluation Results:")
        print(f"{'─'*60}")
        print(f"Latency: {evaluation['latency']:.2f}s")
        print(f"Correctness: {evaluation['correctness_score']:.2f}")
        print(f"Hallucination Rate: {evaluation['hallucination_rate']:.2f} ({evaluation['hallucination_severity']})")
        print(f"Tool Usage: {evaluation['tool_usage_score']:.2f} ({evaluation['tools_used']} tools used)")
        print(f"Trajectory: {evaluation['trajectory_score']:.2f}")
        
        if evaluation.get('hallucination_detected'):
            print("\n Hallucinations Detected:")
            for example in evaluation.get('hallucination_examples', [])[:3]:
                print(f"   - {example}")
        
        print(f"{'─'*60}")
    
    def run_evaluation(self, test_cases: List[str]) -> Dict[str, Any]:
        """
        Run evaluation on multiple test cases
        
        Args:
            test_cases: List of questions to evaluate
            
        Returns:
            Dictionary with aggregate results
        """
        print(f"\n{'='*60}")
        print("LangChain Agent Evaluation with LLM-as-Judge")
        print(f"{'='*60}")
        print(f"Test cases: {len(test_cases)}")
        print(f"Judge model: {self.judge_model}")
        
        results = []
        
        for idx, question in enumerate(test_cases, 1):
            print(f"\n[{idx}/{len(test_cases)}]")
            result = self.evaluate_single_query(question)
            results.append(result)
            time.sleep(1)  # Brief pause between evaluations
        
        # Calculate aggregate metrics
        aggregate = self._calculate_aggregate_metrics(results)
        
        # Save results
        self._save_results(results, aggregate)
        
        # Print final summary
        self._print_final_summary(aggregate)
        
        return {
            "results": results,
            "aggregate": aggregate
        }
    
    def _calculate_aggregate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate metrics from results"""
        successful = [r for r in results if r.get("status") == "success"]
        
        if not successful:
            return {"error": "No successful evaluations"}
        
        aggregate = {
            "total_queries": len(results),
            "successful_queries": len(successful),
            "failed_queries": len(results) - len(successful),
            "success_rate": len(successful) / len(results),
            
            # Correctness metrics
            "avg_correctness": sum(r["correctness_score"] for r in successful) / len(successful),
            "min_correctness": min(r["correctness_score"] for r in successful),
            "max_correctness": max(r["correctness_score"] for r in successful),
            
            # Latency metrics
            "avg_latency": sum(r["latency"] for r in successful) / len(successful),
            "min_latency": min(r["latency"] for r in successful),
            "max_latency": max(r["latency"] for r in successful),
            
            # Hallucination metrics
            "avg_hallucination_rate": sum(r["hallucination_rate"] for r in successful) / len(successful),
            "hallucinations_detected": sum(1 for r in successful if r["hallucination_detected"]),
            "hallucination_detection_rate": sum(1 for r in successful if r["hallucination_detected"]) / len(successful),
            
            # Tool usage metrics
            "avg_tool_usage_score": sum(r["tool_usage_score"] for r in successful) / len(successful),
            "total_tools_used": sum(r["tools_used"] for r in successful),
            "avg_tools_per_query": sum(r["tools_used"] for r in successful) / len(successful),
            
            "avg_trajectory_score": sum(r["trajectory_score"] for r in successful) / len(successful),
            "min_trajectory_score": min(r["trajectory_score"] for r in successful),
            "max_trajectory_score": max(r["trajectory_score"] for r in successful),
            
            # Overall score (weighted)
            "overall_score": (
                sum(r["correctness_score"] for r in successful) * 0.3 +
                sum(max(0, 1 - r["latency"] / 10) for r in successful) * 0.15 +
                sum(1 - r["hallucination_rate"] for r in successful) * 0.25 +
                sum(r["tool_usage_score"] for r in successful) * 0.15 +
                sum(r["trajectory_score"] for r in successful) * 0.15
            ) / len(successful),
            
            "timestamp": datetime.now().isoformat()
        }
        
        return aggregate
    
    def _save_results(self, results: List[Dict[str, Any]], aggregate: Dict[str, Any]):
        """Save results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save Markdown
        self._save_markdown_report(results, aggregate, timestamp)
        
        print("\n Results saved:")
        print("   - llm_judge_evaluation.md")
    
    def _save_markdown_report(self, results: List[Dict[str, Any]], 
                             aggregate: Dict[str, Any], timestamp: str):
        """Save markdown report"""
        
        filename = "llm_judge_evaluation.md"
        
        with open(filename, "w") as f:
            f.write("# LangChain Agent Evaluation - LLM-as-Judge\n\n")
            f.write(f"**Evaluation Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Judge Model**: {self.judge_model}\n")
            f.write(f"**Total Test Cases**: {aggregate['total_queries']}\n\n")
            f.write("---\n\n")
            
            # Executive Summary
            f.write("## Executive Summary\n\n")
            f.write(f"- **Success Rate**: {aggregate['success_rate']:.2%}\n")
            f.write(f"- **Overall Score**: {aggregate['overall_score']:.2%}\n\n")
            
            # Key Metrics
            f.write("## Key Metrics\n\n")
            
            f.write("### Correctness (LLM-as-Judge)\n\n")
            f.write(f"- **Average**: {aggregate['avg_correctness']:.3f}\n")
            f.write(f"- **Min**: {aggregate['min_correctness']:.3f}\n")
            f.write(f"- **Max**: {aggregate['max_correctness']:.3f}\n\n")
            
            f.write("### Hallucination Detection (LLM-as-Judge)\n\n")
            f.write(f"- **Average Rate**: {aggregate['avg_hallucination_rate']:.3f}\n")
            f.write(f"- **Cases with Hallucinations**: {aggregate['hallucinations_detected']}/{aggregate['successful_queries']}\n")
            f.write(f"- **Detection Rate**: {aggregate['hallucination_detection_rate']:.2%}\n\n")
            
            f.write("### Latency\n\n")
            f.write(f"- **Average**: {aggregate['avg_latency']:.2f}s\n")
            f.write(f"- **Min**: {aggregate['min_latency']:.2f}s\n")
            f.write(f"- **Max**: {aggregate['max_latency']:.2f}s\n\n")
            
            f.write("### Tool Usage (LLM-as-Judge)\n\n")
            f.write(f"- **Average Score**: {aggregate['avg_tool_usage_score']:.3f}\n")
            f.write(f"- **Total Tools Used**: {aggregate['total_tools_used']}\n")
            f.write(f"- **Avg Tools per Query**: {aggregate['avg_tools_per_query']:.1f}\n\n")
            
            f.write("### Trajectory Accuracy\n\n")
            f.write(f"- **Average Score**: {aggregate['avg_trajectory_score']:.3f}\n")
            f.write(f"- **Min**: {aggregate['min_trajectory_score']:.3f}\n")
            f.write(f"- **Max**: {aggregate['max_trajectory_score']:.3f}\n\n")
            
            f.write("---\n\n")
            
            # Detailed Results
            f.write("## Detailed Test Results\n\n")
            
            for idx, result in enumerate(results, 1):
                status = "✅" if result.get("status") == "success" else "❌"
                f.write(f"### {status} Test {idx}\n\n")
                f.write(f"**Question**: {result['question']}\n\n")
                
                if result.get("status") == "success":
                    f.write("**Metrics**:\n\n")
                    f.write(f"- **Correctness**: {result['correctness_score']:.3f}\n")
                    f.write(f"  - Reasoning: {result.get('correctness_reasoning', 'N/A')}\n")
                    
                    f.write(f"- **Hallucination Rate**: {result['hallucination_rate']:.3f} ({result['hallucination_severity']})\n")
                    if result.get('hallucination_detected'):
                        f.write("  - Hallucinations detected\n")
                        for ex in result.get('hallucination_examples', [])[:2]:
                            f.write(f"    - {ex}\n")
                    f.write(f"- **Trajectory Accuracy**: {result['trajectory_score']:.3f}\n")
                    f.write(f"- **Latency**: {result['latency']:.2f}s\n")
                    f.write(f"- **Tool Usage**: {result['tool_usage_score']:.3f} ({result['tools_used']} tools)\n")
                    f.write(f"  - Efficiency: {result.get('tool_efficiency', 'N/A')}\n")
                else:
                    f.write(f"**Error**: {result.get('error', 'Unknown error')}\n")
                
                f.write("\n---\n\n")
            
            f.write("*Report generated by LLM-as-Judge Evaluation Framework*\n")
    
    def _print_final_summary(self, aggregate: Dict[str, Any]):
        """Print final summary"""
        print(f"\n{'='*60}")
        print("Evaluation Complete!")
        print(f"{'='*60}")
        print("\n✓ Final Results:")
        print(f"  Success Rate: {aggregate['success_rate']:.2%}")
        print(f"  Overall Score: {aggregate['overall_score']:.2%}")
        print(f"  Avg Correctness: {aggregate['avg_correctness']:.3f}")
        print(f"  Avg Hallucination Rate: {aggregate['avg_hallucination_rate']:.3f}")
        print(f"  Hallucinations Detected: {aggregate['hallucinations_detected']}/{aggregate['successful_queries']}")
        print(f"  Avg Latency: {aggregate['avg_latency']:.2f}s")
        print(f"  Avg Tool Usage: {aggregate['avg_tool_usage_score']:.3f}")
        print(f"  Avg Trajectory: {aggregate['avg_trajectory_score']:.3f}")

        print()


def main():
    """Main evaluation function"""
    
    # Define test cases
    test_cases = [
        "what is the latest finance news?",
        "what are the top tech stocks today?",
        "who is the current president of the United States?",
        "explain quantum computing in simple terms",
        "what is the weather like in Tokyo today?"
    ]
    
    # Create evaluator
    evaluator = LLMJudgeEvaluator(
        judge_model="anthropic.claude-3-5-sonnet-20240620-v1:0"
    )
    
    # Run evaluation
    evaluator.run_evaluation(test_cases)


if __name__ == "__main__":
    main()
