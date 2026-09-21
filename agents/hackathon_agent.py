import json
import logging
from typing import Dict, Any, List, Optional
from tools.hackathon_tools import fetch_devpost_hackathons, format_hackathon_summary
from agents.llm_client import call_llm

logger = logging.getLogger(__name__)

class HackathonAgent:
    """Specialist sub-agent for scouting live hackathons, mentoring, and crafting winning project roadmaps."""

    def __init__(self, model: Optional[str] = None):
        self.name = "Hackathon Scout & Mentor Specialist"
        self.model = model

    def run(self, task_description: str, critique: Optional[str] = None) -> Dict[str, Any]:
        """Executes hackathon scouting or mentoring based on user task intent.
        
        Args:
            task_description: The user request or hackathon topic.
            critique: Optional critique from EvaluatorAgent for self-correction.
            
        Returns:
            Dict containing subagent name, output report, sources, and trajectory.
        """
        trajectory = []
        task_lower = task_description.lower()

        # Determine mode: Mentoring/Roadmapping vs Scouting
        mentoring_keywords = [
            "roadmap", "idea", "winning", "mentor", "pitch", "readme", "architecture",
            "stack", "48h", "24h", "রোডম্যাপ", "আইডিয়া", "প্রজেক্ট", "পিচ", "জিতব", "পরিকল্পনা"
        ]
        is_mentoring = any(k in task_lower for k in mentoring_keywords)

        if is_mentoring:
            # -------------------------------------------------------------
            # Mode 2: Hackathon Mentoring & Execution Roadmap
            # -------------------------------------------------------------
            trajectory.append({"action": "mentoring_strategy_analysis", "target": task_description})

            # Retrieve background hackathons or themes if a specific competition is mentioned
            hackathons = fetch_devpost_hackathons(task_description, limit=3)
            sources = [h["url"] for h in hackathons if h.get("url")]

            mentor_prompt = f"""You are the World's Leading Hackathon Mentor & Chief Judge.
Analyze this hackathon challenge or topic and craft an elite, winning competition blueprint.
Task: {task_description}

Context & Active Competitions:
{format_hackathon_summary(hackathons)}

{f'CRITICAL - QA Critique to Fix from previous iteration: {critique}' if critique else ''}

Generate an exhaustive, highly practical blueprint containing:
1. 💡 **Top 3 Winning Project Ideas**:
   - Give each idea a catchy name, core problem statement, why it will stand out to judges (Novelty + Real-world Impact), and alignment with Google 2026 Whitepaper agentic architectures.
2. ⏱️ **48-Hour Milestone Execution Timeline**:
   - Hour 0–12: Spec-Driven Design, API keys, basic prototype.
   - Hour 12–24: Core multi-agent loop, tool integration, database.
   - Hour 24–36: Frontend UI, error handling, automated evaluation.
   - Hour 36–48: Demo video recording, polish, pitch deck, and submission.
3. 🛠️ **Recommended Tech Stack & Architecture**:
   - Best language, LLM/Agent SDK (Gemini 3.5, LiteLLM, LangGraph), UI (Streamlit / Next.js), and hosting.
4. 🎤 **Winning Pitch Deck Outline & Submission README Template**:
   - 7-slide pitch deck structure.
   - Markdown code snippet for the official GitHub/Devpost README.

Instructions:
- Respond in clear, inspiring Bengali with technical terms in English where appropriate.
- Ensure ideas are realistic for a 24h-48h build while appearing visionary to hackathon judges.
"""
            report = call_llm(
                messages=[{"role": "user", "content": mentor_prompt}],
                model=self.model,
                temperature=0.4
            )

            return {
                "subagent": self.name,
                "output": report,
                "sources": sources,
                "trajectory": trajectory
            }

        else:
            # -------------------------------------------------------------
            # Mode 1: Hackathon Scouting
            # -------------------------------------------------------------
            trajectory.append({"action": "fetch_devpost_hackathons", "query": task_description})
            hackathons = fetch_devpost_hackathons(task_description, limit=5)
            sources = [h["url"] for h in hackathons if h.get("url")]
            summary_markdown = format_hackathon_summary(hackathons)

            scout_prompt = f"""You are an elite Hackathon Scout and Talent Advisor.
The user is looking for active, live, or upcoming hackathons and competitions.

User Request: {task_description}

Raw Hackathon Data:
{summary_markdown}

{f'CRITICAL - QA Critique to Fix: {critique}' if critique else ''}

Instructions:
1. Present the structured comparative table of top hackathons (Name, Prize Pool, Deadline, Platform, Registration Link).
2. For each hackathon, explain:
   - What the challenge is about.
   - Why it is worth participating in.
   - Recommended preparation steps and eligibility.
3. Conclude with tailored recommendations on which hackathon best matches the user's profile and how our AI Assistant squad can mentor them to build a winning project.
4. Write fluently in clear, polite Bengali with professional formatting.
"""
            report = call_llm(
                messages=[{"role": "user", "content": scout_prompt}],
                model=self.model,
                temperature=0.3
            )

            return {
                "subagent": self.name,
                "output": report,
                "sources": sources,
                "trajectory": trajectory
            }
