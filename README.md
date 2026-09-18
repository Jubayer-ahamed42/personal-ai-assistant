# 🤖 Personal Multi-Agent Assistant

A spec-driven, hierarchical personal assistant architecture built following the principles of **Agentic Engineering** from the 2026 Google White Papers.

## 🌟 Key Features

1. **Master Orchestrator**: Receives high-level human orders, decomposes intent into atomic sub-tasks, and coordinates specialized sub-agents.
2. **Specialized Sub-Agent Squad**:
   - **Research & Fact-Checking Specialist**: Web search, content scraping, and source citation.
   - **Code & Automation Specialist**: Python script generation with automated sandbox verification.
   - **Data Analytics Specialist**: Data transforms, exact statistical calculations without LLM arithmetic errors.
3. **Two-Tier Quality & Self-Correction Gate (Evaluator Agent)**:
   - **Tier 1 (Deterministic)**: AST syntax parsing, test execution, and schema validation.
   - **Tier 2 (LLM-as-a-Judge)**: Semantic rubric scoring across Intent Satisfaction, Factuality, and Structure.
   - **Self-Repair Loop**: Automatically feeds critique back to sub-agents to fix mistakes until quality passes before delivering the final report.
4. **Persistent SQLite Memory**: Stores user preferences/rules, session history, and full audit trajectories.
5. **Interactive Web Dashboard**: Streamlit UI with real-time sub-agent tracking and model selection.

---

## 🚀 Quick Start

### 1. Configure API Key
Open `.env` in this directory and paste your API key (at least one):
```env
GEMINI_API_KEY=your_key_here
```
*(You can also configure or change keys anytime directly from the Web UI sidebar)*

### 2. Run Application
Double-click `run_app.bat` or run in terminal:
```bash
.venv\Scripts\activate
streamlit run app.py
```

### 3. Run Automated Tests
```bash
.venv\Scripts\activate
pytest tests/ -v
```
