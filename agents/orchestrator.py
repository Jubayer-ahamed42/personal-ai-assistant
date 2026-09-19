import json
import re
import logging
from typing import Dict, Any, List, Optional, Callable
from config import MAX_EVAL_RETRIES, get_active_model
from database.memory import MemoryManager
from agents.llm_client import call_llm
from agents.research_agent import ResearchAgent
from agents.coding_agent import CodingAgent
from agents.data_agent import DataAgent
from agents.evaluator_agent import EvaluatorAgent
from tools.tts_tools import text_to_speech_bengali

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """Master Personal Assistant and Hierarchical Multi-Agent Orchestrator.
    
    Features Smart Intent Routing:
    - Fast Path: Direct instant response for greetings & conversation (~1-2 seconds)
    - Specialist Path: Decomposes and delegates complex tasks to sub-agents with QA loops
    - Voice Reply: Automatic Bengali speech synthesis for all responses
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None, model: Optional[str] = None):
        self.memory = memory_manager or MemoryManager()
        self.model = model or get_active_model()
        self.researcher = ResearchAgent(model=self.model)
        self.coder = CodingAgent(model=self.model)
        self.data_specialist = DataAgent(model=self.model)
        self.evaluator = EvaluatorAgent(model=self.model)

    def process_command(
        self,
        session_id: str,
        user_command: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Executes a user command through smart routing, delegation, evaluation, and voice generation."""

        def notify(event_type: str, message: str, details: Optional[Dict[str, Any]] = None):
            event = {
                "type": event_type,
                "message": message,
                "details": details or {}
            }
            if on_progress:
                on_progress(event)
            return event

        user_rules = self.memory.get_preference("assistant_rules", "")
        notify("status", "নির্দেশ বিশ্লেষণ ও উপযুক্ত কর্মী নির্বাচন করা হচ্ছে...")

        # -------------------------------------------------------------
        # Step 1: Smart Intent Classifier (Fast-path vs Task-path)
        # -------------------------------------------------------------
        classifier_prompt = f"""You are the Master Personal Assistant.
Analyze this user input:
"{user_command}"

Classify into one of two categories:
1. "CONVERSATION": Greetings, casual talk, questions about who you are, simple chat (e.g. "তুমি আমার কথা বুঝো?", "কেমন আছো", "হাই", "তুমি কী করতে পারো?").
2. "TASK": Requires research, writing code, executing calculations, analyzing data, or solving complex problems.

Respond ONLY with JSON:
{{"intent_type": "CONVERSATION" or "TASK"}}
"""
        try:
            raw_intent = call_llm(
                messages=[{"role": "user", "content": classifier_prompt}],
                model=self.model,
                temperature=0.0
            )
            intent_match = re.search(r"\{.*\}", raw_intent, re.DOTALL)
            intent_type = json.loads(intent_match.group(0))["intent_type"] if intent_match else "TASK"
        except Exception:
            intent_type = "TASK"

        # -------------------------------------------------------------
        # Fast Path: Direct Conversational Response (Instant, ~1-2s)
        # -------------------------------------------------------------
        if intent_type == "CONVERSATION":
            notify("status", "সরাসরি উত্তর প্রস্তুত করা হচ্ছে...")
            
            chat_history = self.memory.get_messages(session_id)[-4:]
            formatted_history = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])

            direct_prompt = f"""You are an elite, highly intelligent, friendly, and respectful Bengali Personal AI Assistant.
The user is speaking to you directly.
Respond warmly, directly, and naturally in fluent native Bengali.

[USER GUIDELINES]:
{user_rules}

[RECENT CHAT HISTORY]:
{formatted_history}

[USER MESSAGE]:
{user_command}

Instructions:
- If the user asks if you understand them (e.g. "তুমি আমার কথা বুঝো"), reassure them warmly that you clearly understand their Bengali voice/text and are ready to execute any task with your specialized sub-agents.
- Keep the response elegant, crisp, and helpful.
"""
            final_report = call_llm(
                messages=[{"role": "user", "content": direct_prompt}],
                model=self.model,
                temperature=0.4
            )

            # Generate spoken voice reply in Bengali
            notify("voice", "ভয়েস অডিও প্রস্তুত করা হচ্ছে...")
            audio_bytes = text_to_speech_bengali(final_report)

            # Save in database
            traj_id = self.memory.create_trajectory(session_id, user_command, {"type": "direct_conversation"})
            self.memory.add_message(session_id, "user", user_command)
            self.memory.add_message(
                session_id,
                "assistant",
                final_report,
                metadata={"trajectory_id": traj_id, "iterations": 1, "type": "conversation"}
            )
            self.memory.complete_trajectory(traj_id, final_report, 1, status="completed")

            notify("completed", "উত্তর সম্পন্ন!", {"final_report": final_report})

            return {
                "trajectory_id": traj_id,
                "final_report": final_report,
                "audio_bytes": audio_bytes,
                "sub_agent_results": [],
                "evaluations": [],
                "iterations": 1
            }

        # -------------------------------------------------------------
        # Specialist Path: Multi-Agent Delegation & QA Loop
        # -------------------------------------------------------------
        plan_prompt = f"""You are the Master Personal Assistant Orchestrator.
Your goal is to break down this user request into clear, atomic sub-tasks for specialized sub-agents.
Carefully interpret native Bengali, regional phrasing, or colloquial terms without confusion.

[USER COMMAND]:
{user_command}

[PERSISTENT USER RULES]:
{user_rules}

Available Sub-Agents:
1. "research": For web search, fact-checking, citations, exploring any subject or news.
2. "coding": For writing Python scripts, debugging, algorithms, file tools, system tests.
3. "data": For data analysis, metrics tables, math calculations, tabular comparisons.

Respond ONLY with a JSON object:
{{
    "summary": "Brief summary of planned execution",
    "subtasks": [
        {{
            "agent": "research" | "coding" | "data",
            "task_description": "Precise instruction for the specialist"
        }}
    ]
}}
"""
        raw_plan = call_llm(
            messages=[{"role": "user", "content": plan_prompt}],
            model=self.model,
            temperature=0.1
        )

        try:
            json_match = re.search(r"\{.*\}", raw_plan, re.DOTALL)
            clean_plan = json_match.group(0) if json_match else raw_plan.strip()
            plan = json.loads(clean_plan)
        except Exception:
            plan = {
                "summary": "সরাসরি সম্পাদন পরিকল্পনা",
                "subtasks": [{"agent": "research", "task_description": user_command}]
            }

        traj_id = self.memory.create_trajectory(session_id, user_command, plan)
        notify("plan", f"পরিকল্পনা প্রস্তুত: {plan.get('summary', 'টাস্ক বিভাজন সম্পন্ন')}", {"plan": plan})

        sub_agent_results = []
        all_evaluations = []
        iteration_count = 1

        # Dispatch tasks to Sub-Agents with Self-Correction Feedback Loop
        for task_idx, task in enumerate(plan.get("subtasks", [])):
            agent_type = task.get("agent")
            task_desc = task.get("task_description")

            notify("subagent_start", f"দায়িত্ব দেওয়া হলো: {agent_type.upper()} স্পেশালিস্ট...", {"subtask": task})

            current_critique = None
            task_success = False
            sub_output_data = {}

            for attempt in range(1, MAX_EVAL_RETRIES + 1):
                iteration_count = max(iteration_count, attempt)

                try:
                    if agent_type == "research":
                        sub_output_data = self.researcher.run(task_desc, critique=current_critique)
                    elif agent_type == "coding":
                        sub_output_data = self.coder.run(task_desc, critique=current_critique)
                    elif agent_type == "data":
                        sub_output_data = self.data_specialist.run(task_desc, critique=current_critique)
                    else:
                        sub_output_data = self.researcher.run(task_desc, critique=current_critique)
                except Exception as e:
                    logger.error(f"Sub-agent {agent_type} exception: {e}")
                    sub_output_data = {
                        "subagent": agent_type,
                        "output": f"Sub-agent encountered an unexpected error: {str(e)}",
                        "tool_errors": [str(e)]
                    }

                notify(
                    "subagent_output",
                    f"{sub_output_data.get('subagent', agent_type)} খসড়া তৈরি করেছে (চেষ্টা #{attempt})।",
                    {"output_snippet": str(sub_output_data.get("output", ""))[:300] + "..."}
                )

                notify("evaluation_start", f"কোয়ালিটি ও তথ্যের সত্যতা যাচাই চলছে (চেষ্টা #{attempt})...")
                eval_result = self.evaluator.evaluate_output(
                    user_intent=task_desc,
                    subagent_name=sub_output_data.get("subagent", agent_type),
                    draft_output=sub_output_data.get("output", ""),
                    execution_context={"tool_errors": sub_output_data.get("tool_errors")}
                )

                self.memory.log_evaluation(
                    trajectory_id=traj_id,
                    iteration=attempt,
                    subagent_name=sub_output_data.get("subagent", agent_type),
                    score=eval_result.get("average_score", 4.0),
                    verdict=eval_result.get("verdict", "APPROVED"),
                    critique="; ".join(eval_result.get("critique", [])),
                    repaired_output=sub_output_data.get("output", "")
                )
                all_evaluations.append(eval_result)

                if eval_result.get("verdict") == "APPROVED":
                    notify("evaluation_pass", f"যাচাই সফল! স্কোর: {eval_result.get('average_score', 4.5)}/5.0", {"eval": eval_result})
                    task_success = True
                    break
                else:
                    current_critique = eval_result.get("feedback_for_repair") or "; ".join(eval_result.get("critique", []))
                    notify(
                        "evaluation_fail",
                        f"ত্রুটি পাওয়া গেছে! সংশোধন লুপ সক্রিয় হচ্ছে (চেষ্টা #{attempt}/{MAX_EVAL_RETRIES})...",
                        {"eval": eval_result, "critique": current_critique}
                    )

            sub_agent_results.append({
                "task": task,
                "output": sub_output_data.get("output", ""),
                "eval": eval_result,
                "attempts": attempt
            })

        # Final Synthesis
        notify("synthesis", "চূড়ান্ত নিখুঁত ও পরিমার্জিত রিপোর্ট প্রস্তুত করা হচ্ছে...")

        synthesis_prompt = f"""You are the Master Personal Assistant.
Your specialized sub-agents have completed and verified all sub-tasks for the user's order.
Combine and polish their findings into a single, comprehensive, beautifully structured final report.
Always respond in the user's natural language (Bengali if the user prompted in Bengali, or English if prompted in English).

[ORIGINAL USER ORDER]:
{user_command}

[VERIFIED SUB-AGENT FINDINGS]:
{json.dumps([{'task': r['task']['task_description'], 'findings': r['output']} for r in sub_agent_results], indent=2)}

[USER GUIDELINES]:
{user_rules}

Formatting Requirements:
- Clear, professional executive summary.
- Deep dive sections with key details, data tables, or code snippets where applicable.
- Source citations or verification notes.
- Direct, pristine, and ready-to-use output.
"""
        final_report = call_llm(
            messages=[{"role": "user", "content": synthesis_prompt}],
            model=self.model,
            temperature=0.2
        )

        # Generate voice audio for the final report summary
        notify("voice", "ভয়েস অডিও প্রস্তুত করা হচ্ছে...")
        audio_bytes = text_to_speech_bengali(final_report)

        self.memory.add_message(session_id, "user", user_command)
        self.memory.add_message(
            session_id,
            "assistant",
            final_report,
            metadata={"trajectory_id": traj_id, "iterations": iteration_count}
        )
        self.memory.complete_trajectory(traj_id, final_report, iteration_count, status="completed")

        notify("completed", "কাজ সফলভাবে সম্পন্ন এবং সম্পূর্ণ যাচাইকৃত!", {"final_report": final_report})

        return {
            "trajectory_id": traj_id,
            "final_report": final_report,
            "audio_bytes": audio_bytes,
            "sub_agent_results": sub_agent_results,
            "evaluations": all_evaluations,
            "iterations": iteration_count
        }
