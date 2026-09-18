import os
import json
import logging
from typing import List, Dict, Any, Optional
import litellm
from config import get_active_model, get_api_key_for_model

# Silence noisy third-party logs
litellm.suppress_debug_info = True
logger = logging.getLogger(__name__)

def call_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    max_tokens: int = 4000
) -> str:
    """Invokes the configured LLM through litellm supporting Gemini, OpenAI, Claude, etc."""
    active_model = model or get_active_model()
    
    # Configure API key dynamically if available
    api_key = get_api_key_for_model(active_model)
    
    kwargs = {
        "model": active_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    if api_key:
        kwargs["api_key"] = api_key
        
    if response_format:
        kwargs["response_format"] = response_format

    try:
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content
        return content or ""
    except Exception as e:
        logger.error(f"LLM Call failed for model {active_model}: {e}")
        # Fallback explanation if API keys are missing
        if "api_key" in str(e).lower() or "authentication" in str(e).lower():
            raise RuntimeError(
                f"API Key Error: Please configure the required API key for '{active_model}' "
                f"in your .env file or via the Web UI Settings."
            )
        raise e
