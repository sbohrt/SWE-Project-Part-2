import os
from typing import Dict, List, cast

from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")

MODEL = os.getenv(
    "LLM_MODEL", "deepseek/deepseek-chat-v3.1:free"
)  # default model if no model specified in .env


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)


def ask_llm(
    messages: List[Dict[str, str]],
    model: str = MODEL,
    temperature: float = 0.0,
) -> str:
    """wrapper for OpenRouter LLMs."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return cast(str, response.choices[0].message.content.strip())
