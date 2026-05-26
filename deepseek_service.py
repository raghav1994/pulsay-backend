"""
DeepSeek API integration for AI-powered comment analysis and suggestions.
Falls back gracefully if the API is unavailable or the key is not set.
"""

from __future__ import annotations

import json
import logging

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

_HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}


def _chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 512) -> str | None:
    """Send a chat request to DeepSeek. Returns the response text or None on failure."""
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set — skipping AI call.")
        return None

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_HEADERS,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("DeepSeek API error: %s", exc)
        return None


def ai_suggestion(distribution: dict, dominant: str, platform: str = "instagram") -> str | None:
    """
    Generate a creator content suggestion using DeepSeek.
    Returns None if the API call fails (caller should fall back to rule-based suggestion).
    """
    dist_summary = ", ".join(f"{k}: {v}%" for k, v in distribution.items())

    messages = [
        {
            "role": "system",
            "content": (
                "You are a sharp, concise creator coach who advises Indian social media creators. "
                "Give ONE punchy, actionable suggestion in 1-2 sentences. "
                "Mix Hindi and English naturally (Hinglish). No bullet points, no preamble."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Platform: {platform}\n"
                f"Audience emotion breakdown — {dist_summary}\n"
                f"Dominant mood: {dominant}\n\n"
                "What should the creator do in their next post?"
            ),
        },
    ]

    return _chat(messages, temperature=0.8, max_tokens=120)


def ai_deep_analysis(
    distribution: dict,
    dominant: str,
    top_positive: list[str],
    top_negative: list[str],
    platform: str = "instagram",
    caption: str = "",
) -> dict | None:
    """
    Run a full AI analysis of a post's comment sentiment.
    Returns a structured dict or None on failure.
    """
    dist_summary = ", ".join(f"{k}: {v}%" for k, v in distribution.items())
    positive_sample = "; ".join(top_positive[:3]) or "none"
    negative_sample = "; ".join(top_negative[:3]) or "none"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert social media analyst for Indian creators. "
                "Respond ONLY with a valid JSON object — no markdown, no explanation outside the JSON. "
                "The JSON must have these exact keys: "
                "\"summary\" (2-3 sentence audience mood summary in Hinglish), "
                "\"insight\" (one key observation about what the audience is feeling), "
                "\"action\" (one concrete next-post recommendation), "
                "\"risk\" (one thing the creator should avoid), "
                "\"sentiment_score\" (integer 0-100, 100 = most positive)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Platform: {platform}\n"
                f"Post caption: {caption or '(not provided)'}\n"
                f"Emotion breakdown: {dist_summary}\n"
                f"Dominant emotion: {dominant}\n"
                f"Top positive comment: {positive_sample}\n"
                f"Top negative comment: {negative_sample}\n\n"
                "Analyse this and return the JSON."
            ),
        },
    ]

    raw = _chat(messages, temperature=0.5, max_tokens=400)
    if not raw:
        return None

    try:
        # Strip accidental markdown fences if DeepSeek wraps JSON in ```
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("DeepSeek returned non-JSON: %s", raw[:200])
        return None
