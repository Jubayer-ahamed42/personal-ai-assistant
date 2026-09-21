import os
import time
import json
import logging
from typing import List, Dict, Any, Optional
import litellm
from config import get_active_model, get_api_key_for_model, sanitize_model_name

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
    raw_model = model or get_active_model()
    active_model = sanitize_model_name(raw_model)
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
            # If daily quota is exhausted, retrying the same model will not help - failover immediately
            if "quota" in err_str or "resource_exhausted" in err_str or "exceeded your current quota" in err_str:
                logger.warning(f"Model {active_model} quota exhausted. Immediately switching to fallback models...")
                break
            # Handle transient high demand (503) or rate limit (429 concurrency)
            elif "503" in err_str or "unavailable" in err_str or "429" in err_str:
                sleep_time = attempt * 1.5
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

    # Automatic fallback cascade for Gemini models (e.g. flash-lite -> flash-latest)
    if "gemini" in active_model:
        fallback_candidates = [
            "gemini/gemini-3.5-flash-lite",
            "gemini/gemini-flash-latest",
            "gemini/gemini-3.6-flash"
        ]
        for fb_model in fallback_candidates:
            if fb_model == active_model:
                continue
            try:
                logger.info(f"Attempting automatic fallback to {fb_model}...")
                fallback_kwargs = kwargs.copy()
                fallback_kwargs["model"] = fb_model
                resp = litellm.completion(**fallback_kwargs)
                if resp and resp.choices and resp.choices[0].message.content:
                    return resp.choices[0].message.content
            except Exception as fb_err:
                logger.debug(f"Fallback model {fb_model} failed: {fb_err}")
                continue

    logger.error(f"All {max_retries} attempts failed for model {active_model}: {last_exception}")
    raise last_exception
