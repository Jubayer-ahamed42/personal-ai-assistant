import os
import logging
from typing import Optional
from google import genai
from google.genai import types
from config import get_api_key_for_model

logger = logging.getLogger(__name__)

def transcribe_audio_to_text(audio_bytes: bytes, mime_type: str = "audio/wav", api_key: Optional[str] = None) -> str:
    """Converts spoken audio (Bengali/English/mixed) to text using Gemini's native audio understanding.
    
    Args:
        audio_bytes: Raw bytes of the recorded voice.
        mime_type: MIME type of audio (e.g., 'audio/wav', 'audio/mp3', 'audio/webm').
        api_key: Optional Gemini API key override.
        
    Returns:
        Accurate transcription text in the user's spoken language.
    """
    key = api_key or os.getenv("GEMINI_API_KEY") or get_api_key_for_model("gemini")
    if not key:
        raise ValueError("Audio transcription requires a GEMINI_API_KEY. Please set it in .env or the sidebar.")

    try:
        client = genai.Client(api_key=key)
        prompt = (
            "You are a native speech recognition expert specializing in Bengali and multilingual audio. "
            "Transcribe this audio recording exactly as spoken. "
            "Carefully capture native Bengali accents, colloquial expressions, dialect variations, and technical terms. "
            "Output ONLY the transcribed text without any prefixes, commentary, or markdown formatting."
        )

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[prompt, audio_part]
        )

        text = response.text.strip() if response.text else ""
        return text
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        raise RuntimeError(f"Voice Recognition Failed: {str(e)}")
