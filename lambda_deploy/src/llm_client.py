import os
from typing import Dict, List

import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

API_KEY = os.getenv("GEN_AI_STUDIO_API_KEY")

# base URL for purdue api
BASE_URL = "https://genai.rcac.purdue.edu/api/chat/completions"

# default model in case env not set
MODEL = os.getenv("LLM_MODEL", "llama3.1:latest")


def ask_llm(
    messages: List[Dict[str, str]],
    model: str = MODEL,
    temperature: float = 0.0,
) -> str:
    """
    General-purpose wrapper for Purdue GenAI Studio using raw requests.
    Sends a list of messages [{role: "user"/"system", content: "..."}]
    and returns the model's text output as a string.
    """
    if not API_KEY:
        raise RuntimeError("Missing GEN_AI_STUDIO_API_KEY in .env")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # parse response
        content = data["choices"][0]["message"]["content"]
        return str(content.strip()) if content else ""

    except requests.exceptions.RequestException as e:
        print(f"[LLM ERROR] Request failed: {e}")
        return ""
    except (KeyError, IndexError) as e:
        print(f"[LLM ERROR] Unexpected response format: {e}")
        return ""
