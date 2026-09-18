import os
import time
import json
import logging
from typing import List, Dict, Any, Optional
import litellm
from config import get_active_model, get_api_key_for_model

litellm.suppress_debug_info = True
logger = logging.getLogger(__name__)

def call_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    max_tokens: int = 4000,
    max_retries: int = 4
) -> str:
    """Invokes the configured LLM through litellm with automatic retry on 503 / 429 rate limits."""
    active_model = model or get_active_model()
    api_key = get_api_key_for_model(active_model)
    
    kwargs = {
        "model": active_model,
        "messages": messages,
        "max_tokens": max_tokens
    }
    
    if api_key:
        kwargs["api_key"] = api_key
        
    if response_format:
        kwargs["response_format"] = response_format

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            err_str = str(e).lower()
            last_exception = e
            # Handle transient high demand (503) or rate limit (429)
            if "503" in err_str or "unavailable" in err_str or "429" in err_str or "quota" in err_str:
                sleep_time = attempt * 2  # 2s, 4s, 6s...
                logger.warning(f"LLM 503/429 transient error on attempt {attempt}. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            elif "api_key" in err_str or "authentication" in err_str:
                raise RuntimeError(
                    f"API Key Error: Please configure the required API key for '{active_model}' "
                    f"in your .env file or via the Web UI Settings."
                )
            else:
                time.sleep(1)

    # Fallback to lite model if primary flash model is under extreme demand spike
    if "gemini" in active_model and active_model != "gemini/gemini-3.5-flash-lite":
        try:
            logger.info("Attempting automatic fallback to gemini/gemini-3.5-flash-lite...")
            fallback_kwargs = kwargs.copy()
            fallback_kwargs["model"] = "gemini/gemini-3.5-flash-lite"
            resp = litellm.completion(**fallback_kwargs)
            return resp.choices[0].message.content or ""
        except Exception:
            pass

    logger.error(f"All {max_retries} attempts failed for model {active_model}: {last_exception}")
    raise last_exception
