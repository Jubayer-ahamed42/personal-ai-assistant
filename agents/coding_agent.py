import re
from typing import Dict, Any, List, Optional
from tools.code_tools import execute_python_code
from tools.file_tools import write_sandbox_file
from agents.llm_client import call_llm

class CodingAgent:
    """Specialist sub-agent for software architecture, coding, testing, and debugging."""

    def __init__(self, model: Optional[str] = None):
        self.name = "Code & Automation Specialist"
        self.model = model

    def run(self, task_description: str, critique: Optional[str] = None) -> Dict[str, Any]:
        """Generates code, runs it in the sandbox to verify functionality, and self-corrects if broken."""
        trajectory = []
        tool_errors = []

        code_prompt = f"""You are an Expert Software Engineer and System Developer.
Your goal is to write clean, complete, production-grade Python code for the following task:
Task: {task_description}

{f'CRITICAL CORRECTION INSTRUCTIONS: {critique}' if critique else ''}

Rules:
1. Provide the complete code inside a ```python ... ``` block.
2. Include runnable verification code/assertions at the end of the script (e.g. `if __name__ == '__main__': ...`) so it can be verified.
3. Keep code modular, robust, and handle potential errors.
"""
        initial_solution = call_llm(
            messages=[{"role": "user", "content": code_prompt}],
            model=self.model,
            temperature=0.2
        )

        # Extract Python code
        code_blocks = re.findall(r"```python(.*?)```", initial_solution, re.DOTALL)
        exec_result = None

        if code_blocks:
            code_to_test = code_blocks[0].strip()
            trajectory.append({"action": "execute_in_sandbox", "status": "running"})
            exec_result = execute_python_code(code_to_test, timeout=15)

            # If execution fails, try an automatic local self-repair cycle
            if not exec_result["success"]:
                tool_errors.append(f"Exit code {exec_result['returncode']}: {exec_result['stderr']}")
                trajectory.append({"action": "self_repair_attempt", "error": exec_result["stderr"]})

                repair_prompt = f"""The previous Python script failed execution in the sandbox with this error:
[ERROR LOG]:
{exec_result['stderr']}

[FAILED SCRIPT]:
{code_to_test}

Fix the script so it executes cleanly without error. Return the corrected complete code in a ```python ... ``` block.
"""
                repaired_solution = call_llm(
                    messages=[{"role": "user", "content": repair_prompt}],
                    model=self.model,
                    temperature=0.1
                )
                repaired_blocks = re.findall(r"```python(.*?)```", repaired_solution, re.DOTALL)
                if repaired_blocks:
                    repaired_code = repaired_blocks[0].strip()
                    re_exec = execute_python_code(repaired_code, timeout=15)
                    if re_exec["success"]:
                        initial_solution = repaired_solution
                        exec_result = re_exec
                        tool_errors.clear()
                        trajectory.append({"action": "self_repair_success", "stdout": re_exec["stdout"]})
                    else:
                        tool_errors.append(f"Repair attempt also failed: {re_exec['stderr']}")

        return {
            "subagent": self.name,
            "output": initial_solution,
            "execution_result": exec_result,
            "tool_errors": tool_errors,
            "trajectory": trajectory
        }
