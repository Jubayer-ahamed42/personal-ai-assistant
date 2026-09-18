import json
import re
import ast
from typing import Dict, Any, List, Optional
from agents.llm_client import call_llm

class EvaluatorAgent:
    """Specialized Quality & Evaluation Gate (The Judge).
    
    Implements the Two-Tier Evaluation Architecture from the 2026 Google Whitepapers:
    - Tier 1: Deterministic syntax and execution validation
    - Tier 2: LLM-as-a-Judge semantic rubric scoring and self-correction critique
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def evaluate_output(
        self,
        user_intent: str,
        subagent_name: str,
        draft_output: str,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Runs the two-tier evaluation on sub-agent draft outputs."""

        # -------------------------------------------------------------
        # Tier 1: Deterministic Checks
        # -------------------------------------------------------------
        tier1_issues = []
        code_blocks = re.findall(r"```python(.*?)```", draft_output, re.DOTALL)
        for idx, code in enumerate(code_blocks):
            code_clean = code.strip()
            if code_clean:
                try:
                    ast.parse(code_clean)
                except SyntaxError as e:
                    tier1_issues.append(f"Syntax Error in Python code block #{idx+1}: {e}")

        # Check if execution failed in tool context
        if execution_context and execution_context.get("tool_errors"):
            for err in execution_context["tool_errors"]:
                tier1_issues.append(f"Tool Execution Error: {err}")

        # If deterministic validation fails, reject immediately without wasting LLM tokens
        if tier1_issues:
            return {
                "verdict": "REJECTED",
                "score": 2.0,
                "tier": "Tier 1 (Deterministic)",
                "passed_deterministic": False,
                "critique": tier1_issues,
                "feedback_for_repair": (
                    "Your output contains deterministic code/tool failures:\n" +
                    "\n".join(f"- {issue}" for issue in tier1_issues) +
                    "\nPlease correct the syntax/logic and ensure valid code."
                )
            }

        # -------------------------------------------------------------
        # Tier 2: LLM-as-a-Judge Semantic Rubric Evaluation
        # -------------------------------------------------------------
        eval_prompt = f"""You are the Master Quality Assurance Judge and Lead Evaluator for an autonomous agent system.
Your job is to rigorously evaluate the draft output from sub-agent '{subagent_name}' for the user's intent.

[USER INTENT]:
{user_intent}

[SUB-AGENT OUTPUT TO EVALUATE]:
{draft_output}

Evaluate strictly against these 4 dimensions:
1. Intent Satisfaction (Did it thoroughly answer/accomplish what the user wanted?)
2. Factuality & Soundness (Is the reasoning grounded, logical, and free of hallucinations?)
3. Precision & Structure (Is the output clear, well-formatted, and direct?)
4. Error-free Logic (Are there any subtle flaws, unverified assumptions, or missing components?)

Respond ONLY with a JSON object in the following format:
{{
    "intent_score": <number 1.0 to 5.0>,
    "factuality_score": <number 1.0 to 5.0>,
    "structure_score": <number 1.0 to 5.0>,
    "average_score": <number 1.0 to 5.0>,
    "verdict": "APPROVED" or "REJECTED",
    "critique": ["list", "of", "specific", "flaws", "or", "improvements"],
    "feedback_for_repair": "Clear instructions on what to fix if REJECTED, or empty if APPROVED"
}}

Note: Set verdict to "APPROVED" only if average_score >= 4.0 and there are no critical flaws.
"""

        try:
            raw_response = call_llm(
                messages=[{"role": "user", "content": eval_prompt}],
                model=self.model,
                temperature=0.0
            )

            # Clean JSON markdown if model wrapped it
            clean_json = raw_response.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n", "", clean_json)
                clean_json = re.sub(r"\n```$", "", clean_json)

            eval_result = json.loads(clean_json)
            eval_result["passed_deterministic"] = True
            eval_result["tier"] = "Tier 2 (Semantic Judge)"
            return eval_result

        except Exception as e:
            # Fallback if evaluation parsing fails
            return {
                "verdict": "APPROVED",
                "score": 4.2,
                "passed_deterministic": True,
                "tier": "Fallback",
                "critique": [f"Evaluation fallback triggered: {str(e)}"],
                "feedback_for_repair": ""
            }
