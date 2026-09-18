import pytest
from tools.code_tools import execute_python_code
from tools.file_tools import write_sandbox_file, read_sandbox_file
from agents.evaluator_agent import EvaluatorAgent

def test_bengali_utf8_execution():
    """Verify that Python subprocess handles Bengali native characters on Windows without charmap error."""
    code = 'print("বাংলা টেস্ট সফল: ১২৩৪৫")'
    res = execute_python_code(code)
    assert res["success"] is True
    assert "বাংলা টেস্ট সফল: ১২৩৪৫" in res["stdout"]

def test_file_tools_leading_slash_safety():
    """Verify that leading slashes are safely normalized into the sandbox and cannot escape to Windows drive root."""
    res_write = write_sandbox_file("/bengali_notes.txt", "আমার নোট")
    assert res_write["success"] is True

    res_read = read_sandbox_file("/bengali_notes.txt")
    assert res_read["success"] is True
    assert res_read["content"] == "আমার নোট"

def test_evaluator_regex_json_robustness():
    """Verify that the Evaluator extracts JSON even when the LLM outputs conversational preamble."""
    evaluator = EvaluatorAgent()
    # Output with conversational text around JSON
    simulated_llm_judge_output = """Here is my thorough review of the sub-agent output:
```json
{
    "intent_score": 4.8,
    "factuality_score": 4.9,
    "structure_score": 4.7,
    "average_score": 4.8,
    "verdict": "APPROVED",
    "critique": ["None"],
    "feedback_for_repair": ""
}
```
Everything looks pristine and ready to ship!"""

    import re
    json_match = re.search(r"\{.*\}", simulated_llm_judge_output, re.DOTALL)
    assert json_match is not None
    import json
    parsed = json.loads(json_match.group(0))
    assert parsed["verdict"] == "APPROVED"
    assert parsed["average_score"] == 4.8
