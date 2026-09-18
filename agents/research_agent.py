import json
from typing import Dict, Any, List, Optional
from tools.search_tools import web_search
from agents.llm_client import call_llm

class ResearchAgent:
    """Specialist sub-agent for information retrieval, web research, and fact-checking."""

    def __init__(self, model: Optional[str] = None):
        self.name = "Research & Fact-Checking Specialist"
        self.model = model

    def run(self, task_description: str, critique: Optional[str] = None) -> Dict[str, Any]:
        """Executes research task using live web search and synthesizes findings."""
        trajectory = []

        # 1. Generate targeted search queries
        query_plan_prompt = f"""You are a deep-research specialist. Given this research task, generate 2-3 optimal search queries.
Task: {task_description}
{f'Previous Critique to Fix: {critique}' if critique else ''}

Respond ONLY with a JSON list of strings, e.g. ["query 1", "query 2"]
"""
        raw_queries = call_llm(
            messages=[{"role": "user", "content": query_plan_prompt}],
            model=self.model,
            temperature=0.1
        )
        
        try:
            clean = raw_queries.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("\n", 1)[0]
            queries = json.loads(clean)
            if not isinstance(queries, list):
                queries = [task_description]
        except Exception:
            queries = [task_description]

        # 2. Perform live search via tools
        search_results = []
        for q in queries[:3]:
            trajectory.append({"action": "web_search", "query": q})
            results = web_search(q, max_results=3)
            search_results.extend(results)

        # 3. Synthesize findings into a structured research memo
        synth_prompt = f"""You are a Lead Research Analyst. Synthesize a comprehensive, fact-grounded research report for the following task.
Task: {task_description}

Web Search Findings:
{json.dumps(search_results, indent=2)}

{f'CRITICAL: You must fix the previous issues identified by QA: {critique}' if critique else ''}

Instructions:
- Provide accurate, well-structured insights with bullet points and clear sections.
- Cite the source titles or URLs where relevant.
- State conclusions objectively and highlight key takeaways.
"""
        report = call_llm(
            messages=[{"role": "user", "content": synth_prompt}],
            model=self.model,
            temperature=0.3
        )

        return {
            "subagent": self.name,
            "output": report,
            "sources": [r.get("url") for r in search_results if r.get("url")],
            "trajectory": trajectory
        }
