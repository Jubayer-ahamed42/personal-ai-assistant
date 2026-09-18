import re
from typing import Dict, Any, List, Optional
from tools.code_tools import execute_python_code
from agents.llm_client import call_llm

class DataAgent:
    """Specialist sub-agent for data analytics, statistical computation, and tabular metrics."""

    def __init__(self, model: Optional[str] = None):
        self.name = "Data Analytics & Calculations Specialist"
        self.model = model

    def run(self, task_description: str, critique: Optional[str] = None) -> Dict[str, Any]:
        """Performs analytical reasoning and verifies computations using Python in the sandbox."""
        trajectory = []
        tool_errors = []

        analysis_prompt = f"""You are a Principal Data Scientist and Quantitative Analyst.
Task: {task_description}

{f'CRITICAL CORRECTION REQUIRED: {critique}' if critique else ''}

Instructions:
1. If calculations, aggregations, or statistical transforms are required, write a self-contained Python script to compute exact values.
2. Provide your findings in structured Markdown tables and bulleted key performance metrics.
3. If code is generated, wrap it in a ```python ... ``` block.
"""
        initial_analysis = call_llm(
            messages=[{"role": "user", "content": analysis_prompt}],
            model=self.model,
            temperature=0.2
        )

        # Check for calculation scripts
        code_blocks = re.findall(r"```python(.*?)```", initial_analysis, re.DOTALL)
        exec_result = None

        if code_blocks:
            calc_script = code_blocks[0].strip()
            trajectory.append({"action": "execute_data_calculation", "status": "running"})
            exec_result = execute_python_code(calc_script, timeout=15)
            if not exec_result["success"]:
                tool_errors.append(f"Calculation Error: {exec_result['stderr']}")
            else:
                trajectory.append({"action": "calculation_succeeded", "output": exec_result["stdout"]})

        return {
            "subagent": self.name,
            "output": initial_analysis,
            "calculation_result": exec_result,
            "tool_errors": tool_errors,
            "trajectory": trajectory
        }
