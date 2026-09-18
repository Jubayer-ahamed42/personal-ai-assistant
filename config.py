import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DB_PATH = BASE_DIR / "database" / "assistant_memory.db"
SANDBOX_PATH = BASE_DIR / os.getenv("SANDBOX_DIR", "sandbox")
SANDBOX_PATH.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Default LLM Settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini/gemini-3.5-flash")
MAX_EVAL_RETRIES = int(os.getenv("MAX_EVAL_RETRIES", "3"))

# Supported Providers & Recommended Models
SUPPORTED_MODELS = {
    "Google Gemini": [
        "gemini/gemini-3.5-flash",
        "gemini/gemini-3.5-flash-lite",
        "gemini/gemini-3.6-flash",
        "gemini/gemini-flash-latest"
    ],
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo"
    ],
    "Anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022"
    ]
}

def get_active_model() -> str:
    return os.getenv("ACTIVE_MODEL", DEFAULT_MODEL)

def get_api_key_for_model(model_name: str) -> str:
    if "gemini" in model_name:
        key = os.getenv("GEMINI_API_KEY", "")
        return key.strip() if key else ""
    elif "gpt" in model_name:
        key = os.getenv("OPENAI_API_KEY", "")
        return key.strip() if key else ""
    elif "claude" in model_name:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        return key.strip() if key else ""
    return ""

def is_configured() -> bool:
    """Checks if at least one API key is present."""
    return bool(
        os.getenv("GEMINI_API_KEY") or 
        os.getenv("OPENAI_API_KEY") or 
        os.getenv("ANTHROPIC_API_KEY")
    )
